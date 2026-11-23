"""Six seeded Egyptian field scenarios — spec Section 6.5 (Cases R1–R6).

`sensors` hold the spec's values. EC values are the root-zone ECe at 25 °C as
written in the spec; the simulator back-calculates a raw (uncompensated) probe
value so the backend's ATC step (formula 2) reproduces the spec ECe exactly.
Fields the spec does not list (PAR, wind, lower-probe EC, O2…) are plausible
simulation fillers and are marked in `fillers`.
"""

from __future__ import annotations

TEST_CASES: list[dict] = [
    {
        "id": "R1",
        "title_en": "Nubaria Calcareous Sand (Seifi — Summer)",
        "title_ar": "رمال النوبارية الجيرية (صيفي)",
        "context": {"region": "nubaria", "season": "seifi", "irrigation_type": "drip", "month": 7},
        "lab": {"texture_class": "desert_sand", "cec_meq": 5.2, "som_pct": 0.35, "caco3_pct": 22.0,
                "esp_pct": 8.0, "water_ec_w": 1.35},
        "sensors": {"vwc_upper": 8.2, "vwc_lower": 7.5, "matric_kpa": 44.0, "soil_temp_c": 33.4,
                    "ece": 2.85, "ph": 8.2, "n": 28, "p": 11, "k": 85, "orp_mv": 440,
                    "air_temp_c": 37.5, "rh_pct": 34.0},
        "spec_vpd_kpa": 4.24,
        "fillers": {"par": 1850, "wind_ms": 4.8, "o2_pct": 18.5, "leaf_wetness_pct": 0.0},
        "expected_top": ["pomegranate"],
        "expected_text_en": "Top Match: Pomegranates. Add: Elemental S (400 kg/fed), compost, acid injection to pH 6.0, Fe-EDDHA, humic acid, +20% leaching water, foliar seaweed + ascorbic acid.",
    },
    {
        "id": "R2",
        "title_en": "Nile Delta Clay Greenhouse (Nili — Autumn)",
        "title_ar": "صوبة طينية بالدلتا (نيلي — خريف)",
        "context": {"region": "nile_delta", "season": "nili", "irrigation_type": "greenhouse", "month": 10},
        "lab": {"texture_class": "clay", "cec_meq": 28.0, "som_pct": 2.4, "caco3_pct": 4.0,
                "esp_pct": 6.0, "water_ec_w": 0.65},
        "sensors": {"vwc_upper": 41.5, "vwc_lower": 40.8, "matric_kpa": 6.0, "soil_temp_c": 21.0,
                    "ece": 1.45, "ph": 7.4, "n": 65, "p": 24, "k": 160, "orp_mv": 145,
                    "air_temp_c": 27.0, "rh_pct": 83.0},
        "spec_vpd_kpa": 0.61,
        "fillers": {"par": 620, "wind_ms": 0.3, "o2_pct": 9.5, "leaf_wetness_pct": 35.0},
        "expected_top": [],
        "expected_alerts": ["R24_WATERLOG", "FUNGAL_RH"],
        "expected_text_en": "Critical Alert: Waterlogging & root hypoxia (ORP < +200 mV) + high fungal RH (> 80%). Halt irrigation, verify drainage, ventilate, then drench Trichoderma + humic acid once drained to FC.",
    },
    {
        "id": "R3",
        "title_en": "Ismailia Sandy Loam (Shetwi — Winter)",
        "title_ar": "طميية رملية بالإسماعيلية (شتوي)",
        "context": {"region": "ismailia", "season": "shetwi", "irrigation_type": "drip", "month": 11},
        "lab": {"texture_class": "sandy_loam", "cec_meq": 14.0, "som_pct": 2.2, "caco3_pct": 2.5,
                "esp_pct": 3.0, "water_ec_w": 0.50},
        "sensors": {"vwc_upper": 17.5, "vwc_lower": 14.0, "matric_kpa": 15.0, "soil_temp_c": 19.2,
                    "ece": 0.85, "ph": 6.3, "n": 55, "p": 32, "k": 140, "orp_mv": 460,
                    "air_temp_c": 21.5, "rh_pct": 64.0},
        "spec_vpd_kpa": 0.92,
        "fillers": {"par": 1100, "wind_ms": 2.1, "o2_pct": 18.0, "leaf_wetness_pct": 0.0},
        "expected_top": ["strawberry", "potato"],
        "expected_text_en": "Top Matches: Strawberries & Potatoes (Ready to Plant, 92–97%). Maintenance micro-fertigation (Tank A: Ca(NO3)2 + Fe-EDDHA; Tank B: SOP + MAP + B/Zn); B-vitamins at transplant.",
    },
    {
        "id": "R4",
        "title_en": "Saline Brackish Well Plot (Seifi — Spring)",
        "title_ar": "قطعة بئر مالح (صيفي — ربيع)",
        "context": {"region": "salheya", "season": "seifi", "irrigation_type": "drip", "month": 4},
        "lab": {"texture_class": "loam", "cec_meq": 18.0, "som_pct": 1.1, "caco3_pct": 14.0,
                "esp_pct": 14.0, "sar": 9.2, "water_ec_w": 1.65},
        "sensors": {"vwc_upper": 22.0, "vwc_lower": 19.5, "matric_kpa": 24.0, "soil_temp_c": 24.8,
                    "ece": 3.40, "ph": 7.9, "n": 48, "p": 19, "k": 110, "orp_mv": 370,
                    "air_temp_c": 34.0, "rh_pct": 48.0},
        "spec_vpd_kpa": 2.77,
        "fillers": {"par": 1650, "wind_ms": 3.9, "o2_pct": 17.0, "leaf_wetness_pct": 0.0},
        "expected_top": ["pomegranate"],
        "expected_disqualified": ["strawberry", "onion"],
        "expected_text_en": "Top Match: Pomegranates (Strawberries/Onions disqualified). Pause fertilizer, 25% leaching, gypsum for ESP > 10%, liquid calcium + humic, Fe-EDDHA.",
    },
    {
        "id": "R5",
        "title_en": "Minya Desert Orchard (Winter Chill / Early Spring)",
        "title_ar": "بستان صحراوي بالمنيا (برودة شتوية / بداية الربيع)",
        "context": {"region": "west_minya", "season": "shetwi", "irrigation_type": "drip", "month": 3,
                    "chill_hours": 230},
        "lab": {"texture_class": "sandy_loam", "cec_meq": 13.0, "som_pct": 1.6, "caco3_pct": 9.0,
                "esp_pct": 5.0, "water_ec_w": 0.78},
        "sensors": {"vwc_upper": 14.8, "vwc_lower": 13.5, "matric_kpa": 31.0, "soil_temp_c": 18.5,
                    "ece": 1.30, "ph": 7.1, "n": 44, "p": 26, "k": 135, "orp_mv": 420,
                    "air_temp_c": 26.0, "rh_pct": 52.0},
        "spec_vpd_kpa": None,
        "fillers": {"par": 1300, "wind_ms": 2.6, "o2_pct": 18.0, "leaf_wetness_pct": 0.0},
        "expected_top": ["grapes", "citrus"],
        "expected_text_en": "Top Matches: Table Grapes & Citrus (chill met). P + Zn at budbreak, pre-bloom Boron, Fe-EDDHA + AMF, compost to lift SOM above 2.0%.",
    },
    {
        "id": "R6",
        "title_en": "Upper Egypt Cool Valley (Shetwi — Winter)",
        "title_ar": "وادٍ بارد بالصعيد (شتوي)",
        "context": {"region": "upper_egypt", "season": "shetwi", "irrigation_type": "drip", "month": 12},
        "lab": {"texture_class": "silt_loam", "cec_meq": 21.0, "som_pct": 2.1, "caco3_pct": 4.5,
                "esp_pct": 4.0, "water_ec_w": 0.55},
        "sensors": {"vwc_upper": 23.2, "vwc_lower": 20.4, "matric_kpa": 19.0, "soil_temp_c": 17.4,
                    "ece": 1.05, "ph": 6.7, "n": 38, "p": 15, "k": 98, "orp_mv": 390,
                    "air_temp_c": 19.0, "rh_pct": 60.0},
        "spec_vpd_kpa": 0.88,
        "fillers": {"par": 950, "wind_ms": 1.8, "o2_pct": 17.5, "leaf_wetness_pct": 0.0},
        "expected_top": ["onion", "potato", "tomato"],
        "expected_text_en": "Top Matches: Onions, Potatoes & Tomatoes. High P (MAP/Phosphoric) + S (SOP) + Zn + Cu; keep shallow 10–20 cm moisture steady.",
    },
]

CASE_BY_ID = {c["id"]: c for c in TEST_CASES}
