"""Virtual sensor simulator — spec Sections 6.5 and 8.3.

Builds Section 6.2 payloads from (a) the six seeded cases R1–R6 and (b) a
random generator with stress modes. Random draws stay inside the Egyptian
agronomic ranges quoted in Part I of the spec.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from ..engine import formulas as f
from ..knowledge.soil import REGIONS, TEXTURES
from ..knowledge.test_cases import CASE_BY_ID

MODES = {
    "random": {"en": "Fully Random Egyptian Farm", "ar": "مزرعة مصرية عشوائية بالكامل"},
    "healthy": {"en": "Healthy Optimal Soil", "ar": "تربة صحية مثالية"},
    "saline": {"en": "High Salinity / Sodicity Stress", "ar": "إجهاد ملوحة / صودية عالية"},
    "alkaline": {"en": "Alkaline Calcareous Lockout", "ar": "انغلاق قلوي جيري"},
    "waterlogged": {"en": "Waterlogging / Hypoxia Risk", "ar": "خطر تشبع مائي / نقص أكسجين"},
    "heatwave": {"en": "Heatwave / Khamsin Stress", "ar": "إجهاد موجة حر / خماسين"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_payload(sensors: dict, fillers: dict, *, device_id: str, farm_id: str, zone_id: str,
                  upper_depth: int = 15, lower_depth: int = 35, battery_v: float = 13.2) -> dict:
    """sensors: vwc_upper, vwc_lower, matric_kpa, soil_temp_c, ece (at 25 °C), ph, n, p, k,
    orp_mv, air_temp_c, rh_pct. EC is converted back to a raw probe value so the
    backend ATC recovers the intended ECe."""
    t_up = sensors["soil_temp_c"]
    t_lo = round(t_up - 1.5, 1)
    ece_up = sensors["ece"]
    ece_lo = round(ece_up * 0.85, 2)
    return {
        "schema_version": "1.0",
        "device_id": device_id,
        "farm_id": farm_id,
        "zone_id": zone_id,
        "timestamp_utc": _now_iso(),
        "hardware_health": {
            "battery_v": battery_v, "solar_charge_ma": fillers.get("solar_ma", 420),
            "signal_rssi_dbm": fillers.get("rssi", -78), "firmware_version": "sim-1.0.0",
            "fault_flags": [],
        },
        "soil_upper": {
            "depth_cm": upper_depth,
            "vwc_pct": sensors["vwc_upper"],
            "matric_potential_kpa": sensors["matric_kpa"],
            "temp_c": t_up,
            "ec_bulk_ds_m": round(f.ec_raw_from_ec25(ece_up, t_up) * 0.47, 3),
            "ec_pore_ds_m": round(f.ec_raw_from_ec25(ece_up, t_up), 3),
            "ph": sensors["ph"],
            "n_ppm": sensors["n"], "p_ppm": sensors["p"], "k_ppm": sensors["k"],
            "orp_mv": sensors["orp_mv"],
            "o2_pct": fillers.get("o2_pct"),
        },
        "soil_lower": {
            "depth_cm": lower_depth,
            "vwc_pct": sensors["vwc_lower"],
            "temp_c": t_lo,
            "ec_pore_ds_m": round(f.ec_raw_from_ec25(ece_lo, t_lo), 3),
        },
        "microclimate": {
            "air_temp_c": sensors["air_temp_c"],
            "rh_pct": sensors["rh_pct"],
            "par_umol_m2_s": fillers.get("par"),
            "leaf_wetness_pct": fillers.get("leaf_wetness_pct"),
            "wind_speed_ms": fillers.get("wind_ms"),
            "rain_mm_hr": fillers.get("rain_mm", 0.0),
        },
    }


def case_bundle(case_id: str) -> dict:
    c = CASE_BY_ID[case_id]
    return {"case": c, "sensors": c["sensors"], "fillers": c["fillers"],
            "lab": dict(c["lab"]), "context": dict(c["context"])}


# ---------------------------------------------------------------------------
# Random generator
# ---------------------------------------------------------------------------
def _u(rng: random.Random, lo: float, hi: float, nd: int = 1) -> float:
    return round(rng.uniform(lo, hi), nd)


def _season_for_month(m: int) -> str:
    if m in (12, 1, 2):
        return "shetwi"
    if m in (5, 6):
        return "seifi"
    if m in (9, 10, 11):
        return "nili"
    return {3: "shetwi", 4: "seifi", 7: "seifi", 8: "nili"}[m]


def random_bundle(mode: str = "random", seed: int | None = None) -> dict:
    rng = random.Random(seed)
    if mode not in MODES:
        mode = "random"
    if mode == "random":
        mode_eff = rng.choice(["healthy", "saline", "alkaline", "waterlogged", "heatwave", "mixed", "mixed"])
    else:
        mode_eff = mode

    # ---- context -------------------------------------------------------------
    region = rng.choice(list(REGIONS))
    month = rng.randint(1, 12)
    irrigation = rng.choice(["drip", "drip", "drip", "greenhouse"])
    texture = rng.choice(list(TEXTURES))
    if mode_eff == "alkaline":
        texture = rng.choice(["calcareous_loam", "desert_sand", "sandy_loam"])
        region = rng.choice(["nubaria", "west_minya", "sadat_city", "toshka", "salheya"])
    elif mode_eff == "waterlogged":
        texture = rng.choice(["clay", "silt_loam", "clay"])
        region = rng.choice(["nile_delta", "qalyubia", "beheira", "sharqia"])
    elif mode_eff == "heatwave":
        month = rng.choice([4, 5, 6])
        irrigation = "drip"
    elif mode_eff == "saline":
        region = rng.choice(["salheya", "ismailia", "nubaria", "toshka", "sadat_city"])
    tex = TEXTURES[texture]
    fc, pwp = tex["fc"], tex["pwp"]

    def vwc_for_awc(awc):
        return round(pwp + (fc - pwp) * awc / 100.0, 1)

    # ---- baseline per mode ---------------------------------------------------
    if mode_eff == "healthy":
        awc = _u(rng, 65, 80); ph = _u(rng, 6.1, 6.9); ece = _u(rng, 0.6, 1.2, 2)
        soil_t = _u(rng, 18, 25); orp = rng.randint(350, 550); air = _u(rng, 18, 28); rh = _u(rng, 50, 70, 0)
        som = _u(rng, 2.0, 3.5, 2); caco3 = _u(rng, 1, 5); esp = _u(rng, 2, 6); ecw = _u(rng, 0.3, 0.7, 2)
    elif mode_eff == "saline":
        awc = _u(rng, 55, 80); ph = _u(rng, 7.6, 8.3); ece = _u(rng, 2.8, 6.0, 2)
        soil_t = _u(rng, 20, 30); orp = rng.randint(300, 480); air = _u(rng, 24, 36); rh = _u(rng, 30, 55, 0)
        som = _u(rng, 0.3, 1.2, 2); caco3 = _u(rng, 5, 20); esp = _u(rng, 10, 22); ecw = _u(rng, 1.3, 2.5, 2)
    elif mode_eff == "alkaline":
        awc = _u(rng, 45, 75); ph = _u(rng, 7.9, 8.6); ece = _u(rng, 1.0, 2.6, 2)
        soil_t = _u(rng, 18, 30); orp = rng.randint(350, 520); air = _u(rng, 20, 34); rh = _u(rng, 30, 60, 0)
        som = _u(rng, 0.2, 1.0, 2); caco3 = _u(rng, 12, 35); esp = _u(rng, 4, 12); ecw = _u(rng, 0.6, 1.4, 2)
    elif mode_eff == "waterlogged":
        awc = 100.0; ph = _u(rng, 7.0, 7.8); ece = _u(rng, 0.9, 2.2, 2)
        soil_t = _u(rng, 14, 24); orp = rng.randint(40, 195); air = _u(rng, 16, 28); rh = _u(rng, 75, 93, 0)
        som = _u(rng, 1.5, 3.0, 2); caco3 = _u(rng, 1, 6); esp = _u(rng, 4, 12); ecw = _u(rng, 0.4, 0.9, 2)
    elif mode_eff == "heatwave":
        awc = _u(rng, 25, 55); ph = _u(rng, 7.0, 8.2); ece = _u(rng, 1.2, 3.2, 2)
        soil_t = _u(rng, 30, 38); orp = rng.randint(380, 560); air = _u(rng, 38, 46); rh = _u(rng, 10, 25, 0)
        som = _u(rng, 0.3, 2.0, 2); caco3 = _u(rng, 2, 20); esp = _u(rng, 3, 12); ecw = _u(rng, 0.5, 1.6, 2)
    else:  # mixed: anything inside Egyptian ranges
        awc = _u(rng, 20, 100); ph = _u(rng, 6.0, 8.6); ece = _u(rng, 0.5, 5.0, 2)
        soil_t = _u(rng, 12, 36); orp = rng.randint(80, 580); air = _u(rng, 8, 44); rh = _u(rng, 12, 92, 0)
        som = _u(rng, 0.2, 3.5, 2); caco3 = _u(rng, 1, 35); esp = _u(rng, 2, 20); ecw = _u(rng, 0.3, 2.4, 2)

    vwc_up = vwc_for_awc(awc) if awc < 100 else round(fc + rng.uniform(0, 3), 1)
    vwc_lo = round(max(pwp, vwc_up - rng.uniform(0.5, 4.0)), 1)
    matric = round(max(1.0, 5 + (100 - min(awc, 100)) * 0.6 + rng.uniform(-4, 4)), 1)
    if mode_eff == "waterlogged":
        matric = _u(rng, 2, 8)
    n = rng.randint(15, 80); p = rng.randint(6, 40); k = rng.randint(70, 260)
    cec = {"desert_sand": (3, 8), "sandy_loam": (8, 15), "loam": (14, 22), "calcareous_loam": (10, 20),
           "silt_loam": (15, 24), "clay": (22, 35)}[texture]
    lab = {
        "texture_class": texture,
        "cec_meq": _u(rng, *cec), "som_pct": som, "caco3_pct": caco3, "esp_pct": esp,
        "sar": round(max(1.0, esp / 1.5 + rng.uniform(-1, 1)), 1),
        "bulk_density": _u(rng, *tex["bd_range"], 2),
        "water_ec_w": ecw, "water_ph": _u(rng, 7.0, 8.2), "water_hco3": _u(rng, 1.0, 5.0),
        "water_boron_ppm": _u(rng, 0.1, 0.9, 2), "water_cl_ppm": rng.randint(40, 320),
    }
    sensors = {
        "vwc_upper": vwc_up, "vwc_lower": vwc_lo, "matric_kpa": matric, "soil_temp_c": soil_t,
        "ece": ece, "ph": ph, "n": n, "p": p, "k": k, "orp_mv": orp,
        "air_temp_c": air, "rh_pct": rh,
    }
    fillers = {
        "par": rng.randint(300, 2000), "wind_ms": _u(rng, 6, 12) if mode_eff == "heatwave" else _u(rng, 0.2, 5),
        "o2_pct": _u(rng, 4, 10) if mode_eff == "waterlogged" else _u(rng, 13, 20),
        "leaf_wetness_pct": _u(rng, 30, 90, 0) if rh > 85 else 0.0,
        "rain_mm": 0.0,
    }
    context = {"region": region, "season": _season_for_month(month), "irrigation_type": irrigation,
               "month": month}
    if month in (1, 2, 3):
        context["chill_hours"] = rng.randint(40, 420)
    return {"mode": mode, "mode_effective": mode_eff, "sensors": sensors, "fillers": fillers,
            "lab": lab, "context": context}
