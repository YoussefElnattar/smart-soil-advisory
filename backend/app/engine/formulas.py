"""Core agronomic formulas — spec Section 7.3 (formulas 1–6).

Pure functions, no I/O. Helpers that are NOT in the spec are grouped at the
bottom under "External helpers" and cite their source.
"""

from __future__ import annotations

import math

from ..knowledge.soil import FEDDAN_M2, TEXTURES

ATC_COEFF = 0.019  # spec formula 2


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# 1. VPD — Tetens equation ----------------------------------------------------
def saturation_vapor_pressure(t_air_c: float) -> float:
    return 0.6108 * math.exp((17.27 * t_air_c) / (t_air_c + 237.3))


def vpd_kpa(t_air_c: float, rh_pct: float) -> float:
    es = saturation_vapor_pressure(t_air_c)
    return es * (1 - rh_pct / 100.0)


# 2. Automatic temperature compensation for EC -------------------------------
def ec25(ec_measured: float, t_soil_c: float) -> float:
    return ec_measured / (1 + ATC_COEFF * (t_soil_c - 25.0))


def ec_raw_from_ec25(ec_at_25: float, t_soil_c: float) -> float:
    """Inverse of formula 2 — used by the simulator to fake an uncompensated probe."""
    return ec_at_25 * (1 + ATC_COEFF * (t_soil_c - 25.0))


# 3. Available Water Capacity -------------------------------------------------
def awc_pct(vwc_measured: float, fc: float, pwp: float) -> float:
    return clamp(((vwc_measured - pwp) / (fc - pwp)) * 100.0, 0.0, 100.0)


def awc_for_texture(vwc_measured: float, texture: str) -> float:
    t = TEXTURES.get(texture, TEXTURES["loam"])
    return awc_pct(vwc_measured, t["fc"], t["pwp"])


# 4. Leaching requirement — FAO-29 -------------------------------------------
LR_MIN, LR_MAX = 0.05, 0.40


def leaching_requirement(ec_w: float, ece_limit: float) -> float:
    denom = 5 * ece_limit - ec_w
    if denom <= 0:
        return LR_MAX
    return clamp(ec_w / denom, LR_MIN, LR_MAX)


# 5. Gross irrigation volume per feddan --------------------------------------
def gross_irrigation_m3_per_feddan(fc: float, vwc_measured: float, root_depth_m: float,
                                   efficiency: float, lr: float = 0.0) -> float:
    deficit = max(0.0, (fc - vwc_measured) / 100.0)
    net = deficit * root_depth_m * FEDDAN_M2
    return net / (efficiency * (1 - lr))


def net_irrigation_m3_per_feddan(fc: float, vwc_measured: float, root_depth_m: float) -> float:
    return max(0.0, (fc - vwc_measured) / 100.0) * root_depth_m * FEDDAN_M2


# 6. Composite Soil Health Index ---------------------------------------------
SHI_WEIGHTS = {"ph": 0.20, "salinity": 0.25, "water": 0.20, "orp": 0.15, "temp": 0.10, "baseline": 0.10}


def _band_score(value: float, lo: float, hi: float, falloff: float) -> float:
    """1 inside [lo, hi]; linear to 0 at `falloff` units outside the band."""
    if lo <= value <= hi:
        return 1.0
    d = lo - value if value < lo else value - hi
    return clamp(1 - d / falloff, 0.0, 1.0)


def soil_health_index(*, ph: float | None, ece: float | None, ece_limit: float,
                      awc: float | None, matric_kpa: float | None, orp_mv: float | None,
                      soil_temp_c: float | None, som_pct: float | None, cec_meq: float | None,
                      ph_window: tuple[float, float] = (6.0, 7.0),
                      awc_window: tuple[float, float] = (60.0, 80.0),
                      tension_window: tuple[float, float] = (10.0, 35.0)) -> dict:
    """Returns {"index": 0-100, "components": {...}}. Missing inputs are skipped and
    the remaining weights are renormalised so a missing optional probe never
    drags the index down."""
    comps: dict[str, float] = {}
    if ph is not None:
        comps["ph"] = _band_score(ph, *ph_window, falloff=2.0)
    if ece is not None:
        comps["salinity"] = 1.0 if ece <= ece_limit else clamp(1 - (ece - ece_limit) / ece_limit, 0.0, 1.0)
    water_parts = []
    if awc is not None:
        water_parts.append(_band_score(awc, *awc_window, falloff=40.0))
    if matric_kpa is not None:
        water_parts.append(_band_score(matric_kpa, *tension_window, falloff=30.0))
    if water_parts:
        comps["water"] = sum(water_parts) / len(water_parts)
    if orp_mv is not None:
        # +300…+600 mV optimal; < +200 mV anaerobic (Table 1.1)
        comps["orp"] = 1.0 if orp_mv >= 300 else clamp((orp_mv - 100) / 200, 0.0, 1.0)
    if soil_temp_c is not None:
        # 18–26 °C optimal; root activity slows < 14 or > 32 °C (Table 1.1)
        t = soil_temp_c
        if 18 <= t <= 26:
            comps["temp"] = 1.0
        elif 14 <= t < 18:
            comps["temp"] = 0.5 + 0.5 * (t - 14) / 4
        elif 26 < t <= 32:
            comps["temp"] = 0.5 + 0.5 * (32 - t) / 6
        else:
            comps["temp"] = clamp(0.5 - min(abs(t - 14), abs(t - 32)) / 10, 0.0, 0.5)
    base_parts = []
    if som_pct is not None:
        base_parts.append(_band_score(som_pct, 2.0, 4.0, falloff=2.0))  # Table 1.2: 2–4 %
    if cec_meq is not None:
        base_parts.append(_band_score(cec_meq, 15.0, 30.0, falloff=12.0))  # Table 1.2: 15–30
    if base_parts:
        comps["baseline"] = sum(base_parts) / len(base_parts)
    total_w = sum(SHI_WEIGHTS[k] for k in comps)
    if total_w == 0:
        return {"index": None, "components": {}}
    index = sum(SHI_WEIGHTS[k] * v for k, v in comps.items()) / total_w * 100
    return {"index": round(index, 1), "components": {k: round(v * 100, 1) for k, v in comps.items()}}


# ---------------------------------------------------------------------------
# External helpers (not in spec — cited)
# ---------------------------------------------------------------------------
def dew_point_c(t_air_c: float, rh_pct: float) -> float:
    """Magnus formula (Alduchov & Eskridge 1996 constants)."""
    rh = clamp(rh_pct, 1.0, 100.0)
    a, b = 17.625, 243.04
    gamma = math.log(rh / 100.0) + a * t_air_c / (b + t_air_c)
    return b * gamma / (a - gamma)


def esp_from_sar(sar: float) -> float:
    """USSL Handbook 60 relation between SAR and ESP."""
    x = -0.0126 + 0.01475 * sar
    if x <= 0:
        return 0.0
    return 100 * x / (1 + x)


def soil_mass_kg_per_feddan(depth_m: float, bulk_density: float) -> float:
    return FEDDAN_M2 * depth_m * bulk_density * 1000.0


def ppm_to_kg_per_feddan(ppm: float, depth_m: float, bulk_density: float) -> float:
    return ppm * soil_mass_kg_per_feddan(depth_m, bulk_density) / 1e6


GYPSUM_EQ_WEIGHT = 86.09  # mg CaSO4·2H2O per meq
GYPSUM_EFFICIENCY = 1.25  # Ca–Na exchange inefficiency factor (USSL / FAO-29 practice)


def gypsum_requirement_kg_per_feddan(esp_now: float, esp_target: float, cec_meq_100g: float,
                                     depth_m: float, bulk_density: float) -> float:
    if esp_now <= esp_target:
        return 0.0
    meq_per_kg = (esp_now - esp_target) / 100.0 * cec_meq_100g * 10.0
    mg_per_kg_soil = meq_per_kg * GYPSUM_EQ_WEIGHT
    kg = mg_per_kg_soil * soil_mass_kg_per_feddan(depth_m, bulk_density) / 1e6
    return kg * GYPSUM_EFFICIENCY


# Spec-range interpolations (ranges from Table 2.4 / Section 7.2) -------------
def elemental_sulfur_kg_per_feddan(ph: float) -> float:
    """Spec gives 300–500 kg/feddan for alkaline soils. Interpolated linearly
    from 300 at pH 7.8 to 500 at pH 8.6 (curve chosen so that R1, pH 8.2, gives the spec's 400 kg)."""
    kg = 300 + (ph - 7.8) * 250
    return round(clamp(kg, 300, 500) / 50) * 50


def compost_m3_per_feddan(som_pct: float) -> float:
    """Spec gives 15–30 m³/feddan when SOM < 2.0%. 30 m³ at SOM ≤ 0.5%, 15 m³ at 2.0%."""
    if som_pct >= 2.0:
        return 0.0
    m3 = 15 + (2.0 - max(som_pct, 0.5)) / 1.5 * 15
    return round(clamp(m3, 15, 30))
