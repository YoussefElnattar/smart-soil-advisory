"""Soil, region, sensor-parameter and fertilizer reference data.

Values come from spec Sections 1, 2 and 6.4 unless marked ``external=True``.
"""

from __future__ import annotations

FEDDAN_M2 = 4200.0  # spec Section 7.3

# ---------------------------------------------------------------------------
# Soil texture profiles (spec Section 6.4 dielectric mapping).
# coarse_index orders textures from coarse (sand) to fine (clay) for the
# texture-similarity score. bulk density ranges: clay & sand from Table 1.2;
# loam-type ranges interpolated (external).
# ---------------------------------------------------------------------------
TEXTURES: dict[str, dict] = {
    "clay": {"en": "Clay (Nile Delta alluvial)", "ar": "طينية (رسوبية الدلتا)", "fc": 40.0, "pwp": 22.0,
             "coarse_index": 4.0, "bd_range": (1.1, 1.4), "external": False},
    "silt_loam": {"en": "Silt Loam", "ar": "طميية سلتية", "fc": 31.0, "pwp": 13.0,
                  "coarse_index": 2.5, "bd_range": (1.2, 1.5), "external": True,
                  "source": "USDA/Saxton-Rawls typical values — silt loam is not in spec Section 6.4"},
    "loam": {"en": "Loam", "ar": "طميية", "fc": 28.0, "pwp": 12.0,
             "coarse_index": 2.0, "bd_range": (1.25, 1.5), "external": False},
    "calcareous_loam": {"en": "Calcareous Loam", "ar": "طميية جيرية", "fc": 26.0, "pwp": 11.0,
                        "coarse_index": 2.0, "bd_range": (1.3, 1.55), "external": False},
    "sandy_loam": {"en": "Sandy Loam", "ar": "طميية رملية", "fc": 20.0, "pwp": 8.0,
                   "coarse_index": 1.0, "bd_range": (1.4, 1.6), "external": False},
    "desert_sand": {"en": "Desert Sand", "ar": "رملية صحراوية", "fc": 13.0, "pwp": 5.0,
                    "coarse_index": 0.0, "bd_range": (1.4, 1.6), "external": False},
}

# ---------------------------------------------------------------------------
# Egyptian regions / governorates (spec Section 4 intro and Table 4.2).
# ---------------------------------------------------------------------------
REGIONS: dict[str, dict] = {
    "nile_delta": {"en": "Nile Delta (Old Lands)", "ar": "دلتا النيل (الأراضي القديمة)", "tags": ["delta", "old_lands"]},
    "qalyubia": {"en": "Qalyubia", "ar": "القليوبية", "tags": ["delta", "old_lands"]},
    "beheira": {"en": "Beheira", "ar": "البحيرة", "tags": ["delta", "old_lands"]},
    "sharqia": {"en": "Sharqia", "ar": "الشرقية", "tags": ["delta", "old_lands"]},
    "nubaria": {"en": "Nubaria (reclaimed)", "ar": "النوبارية (مستصلحة)", "tags": ["desert", "reclaimed"]},
    "ismailia": {"en": "Ismailia (reclaimed)", "ar": "الإسماعيلية (مستصلحة)", "tags": ["desert", "reclaimed", "canal"]},
    "salheya": {"en": "Salheya (reclaimed)", "ar": "الصالحية (مستصلحة)", "tags": ["desert", "reclaimed"]},
    "sadat_city": {"en": "Sadat City (reclaimed)", "ar": "مدينة السادات (مستصلحة)", "tags": ["desert", "reclaimed"]},
    "minya": {"en": "Minya (Nile Valley)", "ar": "المنيا (وادي النيل)", "tags": ["upper_egypt", "old_lands"]},
    "west_minya": {"en": "West Minya (desert)", "ar": "غرب المنيا (صحراوية)", "tags": ["upper_egypt", "desert", "reclaimed"]},
    "assiut": {"en": "Assiut", "ar": "أسيوط", "tags": ["upper_egypt", "old_lands"]},
    "upper_egypt": {"en": "Upper Egypt (Sohag–Aswan)", "ar": "صعيد مصر (سوهاج–أسوان)", "tags": ["upper_egypt", "old_lands"]},
    "toshka": {"en": "Toshka (desert)", "ar": "توشكى (صحراوية)", "tags": ["upper_egypt", "desert", "reclaimed"]},
}


def region_matches(region_id: str | None, targets: list[str]) -> bool:
    if not region_id or not targets:
        return False
    region = REGIONS.get(region_id, {"tags": []})
    return region_id in targets or any(t in targets for t in region["tags"])


# ---------------------------------------------------------------------------
# Table 1.1 — primary real-time probe parameters (reference display + SHI).
# ---------------------------------------------------------------------------
PROBE_PARAMETERS = [
    {"key": "vwc", "en": "Soil Moisture (VWC)", "ar": "رطوبة التربة الحجمية", "unit": "%",
     "tech": "Capacitive, FDR, or TDR dielectric probe", "optimal": "60–80% Available Water Capacity (varies by texture)",
     "role": "Controls irrigation timing; install at 15 cm and 35–45 cm to detect deep percolation."},
    {"key": "matric", "en": "Soil Matric Potential", "ar": "الجهد المائي للتربة", "unit": "kPa",
     "tech": "Tensiometer or granular matrix sensor", "optimal": "10–35 kPa (vegetables); 20–50 kPa (orchards)",
     "role": "Suction roots need to extract water, independent of soil texture. Ideal irrigation trigger."},
    {"key": "soil_temp", "en": "Soil Temperature", "ar": "حرارة التربة", "unit": "°C",
     "tech": "PT100, thermistor, or digital waterproof sensor", "optimal": "18–26 °C (root activity slows < 14 °C or > 32 °C)",
     "role": "Germination, P uptake, mineralization; used for ATC of EC and pH."},
    {"key": "ec", "en": "Electrical Conductivity (ECb / ECp)", "ar": "التوصيل الكهربائي", "unit": "dS/m",
     "tech": "4-electrode titanium or 316L stainless probe", "optimal": "ECe 0.8–2.0 dS/m (crop-specific)",
     "role": "Total dissolved salts and fertilizer concentration; early salinity detection."},
    {"key": "ph", "en": "Soil pH", "ar": "حموضة التربة", "unit": "pH",
     "tech": "ISFET solid-state or rugged glass electrode", "optimal": "6.0–7.0 (most fruits & vegetables)",
     "role": "Master regulator of nutrient availability; Egyptian soils often 7.5–8.5."},
    {"key": "npk", "en": "Macronutrients (N, P, K)", "ar": "العناصر الكبرى", "unit": "mg/kg",
     "tech": "Ion-Selective Electrodes or NIR optical", "optimal": "Crop & growth-stage dependent",
     "role": "Low-cost RS485 NPK probes estimate indirectly and need local lab calibration."},
    {"key": "orp", "en": "Redox Potential (ORP / Eh)", "ar": "جهد الأكسدة والاختزال", "unit": "mV",
     "tech": "Platinum-reference electrode", "optimal": "+300 to +600 mV (well-aerated soil)",
     "role": "Detects waterlogging/anaerobic zones (< +200 mV): denitrification, sulfides, root rot."},
    {"key": "o2", "en": "Soil Oxygen (O2) / CO2", "ar": "أكسجين التربة", "unit": "%",
     "tech": "Optical/galvanic O2 probe", "optimal": "O2 > 12–15%; CO2 < 2%",
     "role": "Roots need oxygen to pump minerals; valuable in heavy Delta clays and substrates."},
]

# Table 1.2 — baseline lab traits.
LAB_TRAITS = [
    {"key": "texture", "en": "Soil Texture (% Sand, Silt, Clay)", "optimal": "Loam or sandy loam",
     "why": "Sets Field Capacity, Wilting Point and probe dielectric curves."},
    {"key": "cec", "en": "Cation Exchange Capacity (CEC)", "optimal": "15–30 meq/100g (sand often 3–8)",
     "why": "Nutrient-holding capacity; low-CEC sands need small, frequent fertigation pulses."},
    {"key": "som", "en": "Soil Organic Matter (SOM)", "optimal": "2.0–4.0% (desert often < 0.5%)",
     "why": "Water retention, aggregate stability, microbes, pH and salinity buffering."},
    {"key": "caco3", "en": "Calcium Carbonate (Active Lime)", "optimal": "< 5% (calcareous soils 10–35%)",
     "why": "Locks pH near 8.0–8.4, iron chlorosis, crusting, phosphate fixation."},
    {"key": "sodicity", "en": "Sodicity (ESP & SAR)", "optimal": "ESP < 10%; SAR < 6",
     "why": "Sodium disperses clay, seals pores, stops infiltration."},
    {"key": "bulk_density", "en": "Bulk Density & Compaction", "optimal": "1.1–1.4 g/cm³ (clay); 1.4–1.6 g/cm³ (sand)",
     "why": "Hardpans restrict roots; signals subsoiling and compost."},
    {"key": "water", "en": "Irrigation Water Quality (ECw, pH, HCO3, B, Cl)", "optimal": "ECw < 0.7–1.2 dS/m; pH 6.0–7.0; B < 0.5 ppm",
     "why": "Brackish wells inject salts, bicarbonate and boron; leaching depends on ECw."},
]

# Section 1.3 — microclimate metrics.
MICROCLIMATE_METRICS = [
    {"key": "vpd", "en": "Air Temperature & RH → VPD", "optimal": "0.8–1.2 kPa vegetative; 1.0–1.5 kPa fruiting",
     "why": "Atmospheric pull on leaves; also GDD and chilling hours (< 7.2 °C)."},
    {"key": "par", "en": "Solar Radiation & PAR", "optimal": "400–700 nm, µmol/m²/s",
     "why": "Photosynthesis and ET0; sunny days need more water, K and Ca."},
    {"key": "leaf_wetness", "en": "Leaf Wetness & Dew Point", "optimal": "Dry foliage",
     "why": "Flags fungal infection windows (late blight, mildews)."},
    {"key": "wind_rain", "en": "Wind Speed & Rain Gauge", "optimal": "—",
     "why": "Khamsin winds spike transpiration; rain pauses scheduled irrigation."},
]

# Table 2.1 — macronutrients for alkaline soils.
MACRONUTRIENTS = [
    {"nutrient": "N", "role": "Chlorophyll, amino acids, canopy expansion, early vigor.",
     "forms": "Ammonium Sulfate (acidifying), Calcium Nitrate (fruiting), Urea (avoid volatilization in hot alkaline soil).",
     "deficiency": "Uniform yellowing on older leaves; stunting. Excess: soft foliage, poor fruit set."},
    {"nutrient": "P", "role": "Root establishment, ATP energy, flower initiation, fruit set.",
     "forms": "Phosphoric Acid (lowers drip pH), MAP, MKP.",
     "deficiency": "Dark green/purplish older leaves; weak roots; delayed flowering. Locked out at pH > 7.5."},
    {"nutrient": "K", "role": "Sugar transport (Brix), fruit sizing, color, stomatal regulation, heat/salt tolerance.",
     "forms": "Potassium Sulfate (SOP), Potassium Nitrate, KTS. Avoid KCl on chloride-sensitive crops.",
     "deficiency": "Scorched margins of older leaves; hollow pale fruit; rapid wilting."},
    {"nutrient": "Ca", "role": "Cell walls, firmness, shelf life, root tips, salinity mitigation.",
     "forms": "Calcium Nitrate (fertigation), Gypsum (sodic reclamation). Never mix with sulfates/phosphates in same tank.",
     "deficiency": "Blossom-end rot, tip burn, fruit cracking; new growth first."},
    {"nutrient": "Mg", "role": "Chlorophyll centre; photosynthesis and P transport.",
     "forms": "Magnesium Sulfate, Magnesium Nitrate. Balance K:Mg.",
     "deficiency": "Interveinal yellowing on older leaves; early leaf drop."},
    {"nutrient": "S", "role": "Protein/enzymes, pungency (onions), soil acidification.",
     "forms": "Elemental Sulfur (pre-plant), Ammonium Sulfate, Potassium Sulfate, Gypsum.",
     "deficiency": "Pale yellowing of young upper leaves."},
]

# Table 2.2 — micronutrients.
MICRONUTRIENTS = [
    {"nutrient": "Fe", "form": "Fe-EDDHA (6% ortho-ortho, stable to pH 10) for soil/drip; Fe-EDTA foliar only.",
     "deficiency": "Bright yellow interveinal chlorosis on youngest leaves."},
    {"nutrient": "Zn", "form": "Zn-EDTA or amino-acid chelate; Zinc Sulfate banded with compost.",
     "deficiency": "Little leaves, short internodes, mottled chlorosis."},
    {"nutrient": "Mn", "form": "Mn-EDTA or Mn-amino chelate (foliar preferred on high-pH soils).",
     "deficiency": "Checkered interveinal chlorosis with necrotic spots."},
    {"nutrient": "B", "form": "Solubor or Boron-ethanolamine (narrow margin — dose carefully).",
     "deficiency": "Flower abortion, hollow fruits, brittle stems, cracked skin."},
    {"nutrient": "Cu", "form": "Cu-EDTA or Copper Sulfate (small targeted doses).",
     "deficiency": "Shoot-tip dieback, bluish wilted leaves, thin onion skins."},
    {"nutrient": "Mo", "form": "Sodium or Ammonium Molybdate (trace amounts).",
     "deficiency": "Whiptail leaves, scorched edges, poor N response."},
]

# Table 2.4 — five sensor-triggered remediation rules (logic lives in engine/alerts.py).
REMEDIATION_RULES = [
    {"code": "R24_PH_ALKALINE", "pattern": "Soil pH > 7.8 (persistent)", "diagnosis": "Alkaline micronutrient & phosphorus lockout"},
    {"code": "R24_EC_SALINE", "pattern": "Soil EC > crop threshold + adequate moisture", "diagnosis": "Root-zone salt accumulation (osmotic stress)"},
    {"code": "R24_DROUGHT_HEAT", "pattern": "Low VWC + Soil Temp > 32 °C", "diagnosis": "Combined drought and root thermal stress"},
    {"code": "R24_WATERLOG", "pattern": "High VWC + Redox < +200 mV", "diagnosis": "Waterlogging & root hypoxia (root rot risk)"},
    {"code": "R24_HIGH_VPD", "pattern": "High VPD (> 1.8 kPa) + normal soil VWC", "diagnosis": "Atmospheric stress outpacing root uptake"},
]

# ---------------------------------------------------------------------------
# Fertilizer catalogue. Nutrient fractions are standard product grades
# (oxide → element conversions: P = P2O5 × 0.4364, K = K2O × 0.8301).
# tank: A = calcium tank, B = phosphate/sulfate tank, ACID = acid tank.
# ---------------------------------------------------------------------------
FERTILIZERS: dict[str, dict] = {
    "calcium_nitrate": {"en": "Calcium Nitrate 15.5-0-0 +19% Ca", "ar": "نترات الكالسيوم", "tank": "A",
                        "n": 0.155, "ca": 0.19, "contains": ["calcium", "nitrate"]},
    "potassium_nitrate": {"en": "Potassium Nitrate 13-0-46", "ar": "نترات البوتاسيوم", "tank": "A",
                          "n": 0.13, "k": 0.382, "contains": ["nitrate"]},
    "fe_eddha": {"en": "Fe-EDDHA 6% (ortho-ortho)", "ar": "حديد مخلبي EDDHA 6%", "tank": "A",
                 "fe": 0.06, "contains": ["chelate"]},
    "ammonium_sulfate": {"en": "Ammonium Sulfate 21-0-0 +24% S", "ar": "سلفات الأمونيوم", "tank": "B",
                         "n": 0.21, "s": 0.24, "contains": ["sulfate", "ammonium"]},
    "map": {"en": "Monoammonium Phosphate (MAP) 12-61-0", "ar": "فوسفات أحادي الأمونيوم MAP", "tank": "B",
            "n": 0.12, "p": 0.2662, "contains": ["phosphate", "ammonium"]},
    "mkp": {"en": "Monopotassium Phosphate (MKP) 0-52-34", "ar": "فوسفات أحادي البوتاسيوم MKP", "tank": "B",
            "p": 0.2269, "k": 0.2822, "contains": ["phosphate"]},
    "sop": {"en": "Potassium Sulfate (SOP) 0-0-50 +18% S", "ar": "سلفات البوتاسيوم", "tank": "B",
            "k": 0.415, "s": 0.18, "contains": ["sulfate"]},
    "mgso4": {"en": "Magnesium Sulfate (Epsom) 9.9% Mg +13% S", "ar": "سلفات الماغنسيوم", "tank": "B",
              "mg": 0.0986, "s": 0.13, "contains": ["sulfate"]},
    "zn_edta": {"en": "Zn-EDTA 15%", "ar": "زنك مخلبي EDTA", "tank": "B", "zn": 0.15, "contains": ["chelate"]},
    "mn_edta": {"en": "Mn-EDTA 13%", "ar": "منجنيز مخلبي EDTA", "tank": "B", "mn": 0.13, "contains": ["chelate"]},
    "cu_edta": {"en": "Cu-EDTA 15%", "ar": "نحاس مخلبي EDTA", "tank": "B", "cu": 0.15, "contains": ["chelate"]},
    "solubor": {"en": "Solubor (20.5% B)", "ar": "سولوبور (بورون 20.5%)", "tank": "B", "b": 0.205, "contains": ["borate"]},
    "phosphoric_acid": {"en": "Phosphoric Acid 85%", "ar": "حمض الفوسفوريك 85%", "tank": "ACID",
                        "p": 0.268, "contains": ["phosphate", "acid"]},
    "nitric_acid": {"en": "Nitric Acid 60%", "ar": "حمض النيتريك 60%", "tank": "ACID",
                    "n": 0.133, "contains": ["nitrate", "acid"]},
    # Listed only so the validator can reject it; the engine never prescribes KCl.
    "potassium_chloride": {"en": "Potassium Chloride (KCl)", "ar": "كلوريد البوتاسيوم", "tank": "B",
                           "k": 0.498, "contains": ["chloride"]},
}

# ---------------------------------------------------------------------------
# EXTERNAL (not in spec): stage targets for soil-available N/P/K (mg/kg) and
# weekly maintenance fertigation (kg nutrient per feddan per week).
# Generic open-field vegetable fertigation guidance; crop modifiers in crops.py.
# ---------------------------------------------------------------------------
STAGE_NPK_TARGET_PPM_EXT = {
    "establishment": {"n": (30, 50), "p": (25, 40), "k": (120, 180)},
    "vegetative": {"n": (50, 80), "p": (20, 35), "k": (140, 200)},
    "flowering": {"n": (40, 60), "p": (20, 35), "k": (180, 250)},
    "ripening": {"n": (25, 45), "p": (15, 30), "k": (200, 280)},
}

STAGE_WEEKLY_KG_EXT = {
    "establishment": {"n": 2.0, "p": 1.5, "k": 2.0, "ca": 1.0, "mg": 0.4},
    "vegetative": {"n": 4.0, "p": 1.5, "k": 4.0, "ca": 2.0, "mg": 0.8},
    "flowering": {"n": 3.5, "p": 1.5, "k": 6.0, "ca": 3.0, "mg": 1.0},
    "ripening": {"n": 2.0, "p": 1.0, "k": 6.0, "ca": 2.5, "mg": 1.0},
}

# Typical weekly chelate rates per feddan (external, label as such).
MICRO_WEEKLY_KG_EXT = {
    "fe_eddha": 1.0,  # doubled when pH > 8.0 or CaCO3 > 10%
    "zn_edta": 0.25,
    "mn_edta": 0.25,
    "cu_edta": 0.1,
    "solubor": 0.25,  # capped — narrow deficiency/toxicity margin (Table 2.2)
}

# Default bulk density by texture when lab value missing (midpoint of range).
def default_bulk_density(texture: str) -> float:
    lo, hi = TEXTURES.get(texture, TEXTURES["loam"])["bd_range"]
    return round((lo + hi) / 2, 2)
