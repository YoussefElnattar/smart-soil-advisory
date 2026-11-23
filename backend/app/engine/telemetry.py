"""Turns a Section 6.2 uplink payload into a validated, derived, flat reading.

- Out-of-physics values are nulled and flagged (Section 6.4 fault detection);
  the rest of the packet is kept so a single bad electrode never corrupts the
  agronomic recommendations.
- ATC (formula 2) is applied unless the node reports `hardware_health.ec_atc_applied`.
- NPK lab-offset calibration (corrected = raw × gain + offset) is applied when
  the zone has coefficients.
"""

from __future__ import annotations

from . import formulas as f

PHYSICS_LIMITS = {
    "ph": (2.0, 13.0),
    "vwc_upper": (0.0, 100.0),
    "vwc_lower": (0.0, 100.0),
    "soil_temp_upper": (-5.0, 65.0),
    "soil_temp_lower": (-5.0, 65.0),
    "matric_kpa": (0.0, 250.0),
    "ec_bulk_upper": (0.0, 30.0),
    "ec_pore_upper": (0.0, 60.0),
    "ec_pore_lower": (0.0, 60.0),
    "orp_mv": (-600.0, 1000.0),
    "o2_pct": (0.0, 25.0),
    "air_temp_c": (-15.0, 60.0),
    "rh_pct": (0.0, 100.0),
    "n_ppm": (0.0, 2000.0),
    "p_ppm": (0.0, 2000.0),
    "k_ppm": (0.0, 3000.0),
}

STUCK_AT_ZERO_KEYS = ["ph", "ec_pore_upper", "vwc_upper", "n_ppm", "p_ppm", "k_ppm"]


def flatten(payload: dict) -> dict:
    up = payload.get("soil_upper") or {}
    lo = payload.get("soil_lower") or {}
    mc = payload.get("microclimate") or {}
    hh = payload.get("hardware_health") or {}
    return {
        "time": payload.get("timestamp_utc"),
        "device_id": payload.get("device_id"),
        "upper_depth_cm": up.get("depth_cm"),
        "lower_depth_cm": lo.get("depth_cm"),
        "vwc_upper": up.get("vwc_pct"),
        "vwc_lower": lo.get("vwc_pct"),
        "matric_kpa": up.get("matric_potential_kpa"),
        "soil_temp_upper": up.get("temp_c"),
        "soil_temp_lower": lo.get("temp_c"),
        "ec_bulk_upper": up.get("ec_bulk_ds_m"),
        "ec_pore_upper": up.get("ec_pore_ds_m"),
        "ec_pore_lower": lo.get("ec_pore_ds_m"),
        "ph": up.get("ph"),
        "n_ppm": up.get("n_ppm"),
        "p_ppm": up.get("p_ppm"),
        "k_ppm": up.get("k_ppm"),
        "orp_mv": up.get("orp_mv"),
        "o2_pct": up.get("o2_pct"),
        "air_temp_c": mc.get("air_temp_c"),
        "rh_pct": mc.get("rh_pct"),
        "par": mc.get("par_umol_m2_s"),
        "leaf_wetness": mc.get("leaf_wetness_pct"),
        "wind_ms": mc.get("wind_speed_ms"),
        "rain_mm": mc.get("rain_mm_hr"),
        "battery_v": hh.get("battery_v"),
        "solar_ma": hh.get("solar_charge_ma"),
        "rssi_dbm": hh.get("signal_rssi_dbm"),
        "firmware_version": hh.get("firmware_version"),
        "ec_atc_applied": bool(hh.get("ec_atc_applied", False)),
        "fault_flags": list(hh.get("fault_flags") or []),
    }


def validate(reading: dict, history: list[dict] | None = None) -> dict:
    faults = list(reading.get("fault_flags") or [])
    for key, (lo, hi) in PHYSICS_LIMITS.items():
        v = reading.get(key)
        if v is None:
            continue
        if not (lo <= v <= hi):
            faults.append(f"{key}_out_of_range({v})")
            reading[key] = None
    # Stuck-at-zero: exact zero now and in the two previous readings.
    hist = history or []
    for key in STUCK_AT_ZERO_KEYS:
        if reading.get(key) == 0 and len(hist) >= 2 and all(h.get(key) == 0 for h in hist[:2]):
            faults.append(f"{key}_stuck_at_zero")
            reading[key] = None
    reading["fault_flags"] = faults
    return reading


def derive(reading: dict, *, texture_fc_pwp: tuple[float, float], npk_calibration: dict | None) -> dict:
    t_up = reading.get("soil_temp_upper")
    t_lo = reading.get("soil_temp_lower") if reading.get("soil_temp_lower") is not None else t_up
    atc_done = reading.get("ec_atc_applied")

    def comp(ec, t):
        if ec is None:
            return None
        if atc_done or t is None:
            return round(ec, 3)
        return round(f.ec25(ec, t), 3)

    reading["ec25_upper"] = comp(reading.get("ec_pore_upper"), t_up)
    reading["ec25_lower"] = comp(reading.get("ec_pore_lower"), t_lo)
    fc, pwp = texture_fc_pwp
    reading["awc_upper"] = None if reading.get("vwc_upper") is None else round(f.awc_pct(reading["vwc_upper"], fc, pwp), 1)
    reading["awc_lower"] = None if reading.get("vwc_lower") is None else round(f.awc_pct(reading["vwc_lower"], fc, pwp), 1)
    if reading.get("air_temp_c") is not None and reading.get("rh_pct") is not None:
        reading["vpd_kpa"] = round(f.vpd_kpa(reading["air_temp_c"], reading["rh_pct"]), 3)
    else:
        reading["vpd_kpa"] = None
    cal = npk_calibration or {}
    reading["npk_calibrated"] = bool(cal)
    for n in ("n", "p", "k"):
        raw = reading.get(f"{n}_ppm")
        c = cal.get(n)
        reading[f"{n}_cal"] = None if (raw is None or not c) else round(max(0.0, raw * c["gain"] + c["offset"]), 1)
    return reading
