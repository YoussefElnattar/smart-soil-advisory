"""Mode B — "What to Add to Your Soil" prescription generator (spec Section 7.2).

Five modules: (1) structural & pH conditioning, (2) irrigation & leaching,
(3) stage-based macronutrients with Tank A / B / Acid split, (4) chelates,
vitamins, biostimulants & biofertilizers, (5) crop hazard alerts.
Items carry `source` and `external` so the UI can show what traces to the
spec and what comes from an outside reference.
"""

from __future__ import annotations

from ..knowledge.crops import CROP_BY_SLUG, STAGE_NAMES, stage_kc, stage_modifier
from ..knowledge.soil import (FERTILIZERS, MICRO_WEEKLY_KG_EXT, STAGE_NPK_TARGET_PPM_EXT,
                              STAGE_WEEKLY_KG_EXT, TEXTURES)
from . import alerts as alert_engine
from . import fertigation
from . import formulas as f
from .state import FieldState

DRIP_EFFICIENCY = 0.90       # spec: 0.85–0.90
OTHER_EFFICIENCY = 0.85
WETTED_FRACTION_EXT = {"drip": 0.5, "greenhouse": 0.6}  # external: share of feddan wetted by emitters
ESP_TARGET = 10.0            # spec Table 1.2: ESP < 10 %


def _item(key, en, ar, amount, unit, timing_en, timing_ar, reason_en, reason_ar, source, external=False):
    return {"key": key, "en": en, "ar": ar, "amount": amount, "unit": unit,
            "timing_en": timing_en, "timing_ar": timing_ar,
            "reason_en": reason_en, "reason_ar": reason_ar, "source": source, "external": external}


# ---------------------------------------------------------------------------
# Module 1 — structural & pH conditioning
# ---------------------------------------------------------------------------
def conditioning(st: FieldState, crop: dict) -> list[dict]:
    out = []
    ph = st.r("ph")
    lab = st.lab
    caco3 = lab.get("caco3_pct")
    perennial = crop["perennial"]
    timing_s_en = "Band under the tree canopy after harvest" if perennial else "Pre-plant: incorporate into the bed"
    timing_s_ar = "تكبيش تحت مسقط الأشجار بعد الحصاد" if perennial else "قبل الزراعة: يخلط بالمهد"
    if ph is not None and ph > 7.5:
        kg = f.elemental_sulfur_kg_per_feddan(ph)
        note_en = f"Soil pH {ph:.1f} > 7.5 locks P, Fe, Zn, Mn."
        note_ar = f"حموضة {ph:.1f} > 7.5 تغلق الفوسفور والحديد والزنك والمنجنيز."
        if caco3 is not None and caco3 > 5:
            note_en += f" Active CaCO3 {caco3:.0f}% buffers the soil — sulfur alone cannot neutralise it; rely on acidified fertigation and Fe-EDDHA too."
            note_ar += f" الجير النشط {caco3:.0f}% يعادل الكبريت — اعتمد أيضاً على التسميد المحمض وحديد EDDHA."
        out.append(_item("sulfur", "Elemental Agricultural Sulfur", "كبريت زراعي عنصري", kg, "kg/feddan",
                         timing_s_en, timing_s_ar, note_en, note_ar, "Table 2.4 / Section 7.2 (300–500 kg/feddan)"))
    water_ph, hco3 = lab.get("water_ph"), lab.get("water_hco3")
    if (ph is not None and ph > 7.5) or (water_ph is not None and water_ph > 7.0) or (hco3 is not None and hco3 > 1.5):
        out.append(_item("acid_injection", "Acid injection target (phosphoric / nitric)", "هدف حقن الحمض (فوسفوريك / نيتريك)",
                         "5.8–6.2", "drip-water pH",
                         "Every fertigation — titrate acid into the Acid tank until the dripper outlet reads pH 5.8–6.2",
                         "مع كل تسميد — عاير الحمض حتى يصل pH ماء النقاط إلى 5.8–6.2",
                         "Neutralises irrigation bicarbonate and keeps P and micronutrients soluble.",
                         "يعادل بيكربونات المياه ويحافظ على ذوبان الفوسفور والعناصر الصغرى.",
                         "Table 2.4 / Section 7.2"))
    som = lab.get("som_pct")
    if som is not None and som < 2.0:
        m3 = f.compost_m3_per_feddan(som)
        out.append(_item("compost", "Matured Organic Compost", "كمبوست عضوي ناضج", m3, "m³/feddan",
                         timing_s_en, timing_s_ar,
                         f"SOM {som:.2f}% < 2.0% — raises water retention, CEC and microbial life.",
                         f"المادة العضوية {som:.2f}% < 2.0% — يرفع الاحتفاظ بالماء والسعة التبادلية والحياة الميكروبية.",
                         "Section 7.2 (15–30 m³/feddan)"))
    esp = st.esp
    sar = lab.get("sar")
    if (esp is not None and esp > ESP_TARGET) or (sar is not None and sar > 6):
        cec = lab.get("cec_meq")
        depth = crop["lower_depth_cm"] / 100.0
        if esp is not None and esp > ESP_TARGET and cec:
            kg = f.gypsum_requirement_kg_per_feddan(esp, ESP_TARGET, cec, depth, st.bulk_density)
            out.append(_item("gypsum", "Agricultural Gypsum (CaSO4·2H2O)", "جبس زراعي", round(kg / 50) * 50, "kg/feddan",
                             "Before the leaching cycle; incorporate in the root zone",
                             "قبل دورة الغسيل؛ يخلط في منطقة الجذور",
                             f"ESP {esp:.1f}% > 10% — sodium disperses clay and seals pores. GR = (ESP−10)/100 × CEC × soil mass × 86 mg/meq × 1.25.",
                             f"الصوديوم المتبادل {esp:.1f}% > 10% — يفكك الطين ويسد المسام.",
                             "Section 7.2 trigger; gypsum-requirement equation is external (USSL Handbook 60)", external=True))
        else:
            out.append(_item("gypsum_watch", "Gypsum — monitor sodicity", "الجبس — مراقبة الصودية", None, "",
                             "Re-test ESP next season", "أعد قياس ESP الموسم القادم",
                             f"SAR {sar} > 6 but ESP is within limit — no gypsum dose calculated yet.",
                             f"SAR {sar} > 6 لكن ESP ضمن الحد — لا جرعة جبس حالياً.", "Table 1.2"))
    bd = lab.get("bulk_density")
    if bd is not None and bd > TEXTURES[st.texture]["bd_range"][1]:
        out.append(_item("subsoil", "Subsoiling / chisel plowing", "حرث تحت التربة / حرث حفار", None, "",
                         "Before planting, when soil is friable", "قبل الزراعة والتربة مستحرثة",
                         f"Bulk density {bd:.2f} g/cm³ is above the {TEXTURES[st.texture]['en']} range — compacted hardpan.",
                         f"الكثافة الظاهرية {bd:.2f} أعلى من المدى — طبقة صماء.", "Table 1.2 / Section 7.2"))
    return out


# ---------------------------------------------------------------------------
# Module 2 — irrigation & salinity leaching
# ---------------------------------------------------------------------------
def leaching_fraction(ece: float | None, limit: float, ec_w: float | None) -> tuple[float, str]:
    if ece is None:
        return 0.0, "none"
    ratio = ece / limit
    if ratio >= 1.0:
        band = 0.20 + min((ratio - 1.0) / 0.4, 1.0) * 0.05
        state = "exceeds"
    elif ratio >= 0.8:
        band = 0.15 + (ratio - 0.8) / 0.2 * 0.05
        state = "approaching"
    else:
        return 0.0, "safe"
    if ec_w is not None and ec_w > 1.2:  # brackish well (Table 1.2 ECw limit 0.7–1.2)
        band += 0.05
    band = min(band, 0.25)  # spec: +15–25 % extra water
    lr = f.leaching_requirement(ec_w, limit) if ec_w is not None else 0.0
    return min(max(band, lr), f.LR_MAX), state


def irrigation(st: FieldState, crop: dict, alerts: list[dict]) -> dict:
    eff = DRIP_EFFICIENCY if st.context.get("irrigation_type", "drip") == "drip" else OTHER_EFFICIENCY
    root_depth = crop["lower_depth_cm"] / 100.0
    vwc = st.r("vwc_upper")
    lf, salinity_state = leaching_fraction(st.ece, crop["ec_limit"], st.lab.get("water_ec_w"))
    codes = {a["rule_code"] for a in alerts}
    halt = "R24_WATERLOG" in codes or "PEPPER_PHYTO" in codes or (vwc is not None and vwc >= st.fc)
    net = gross = 0.0
    if vwc is not None and not halt:
        net = f.net_irrigation_m3_per_feddan(st.fc, vwc, root_depth)
        gross = f.gross_irrigation_m3_per_feddan(st.fc, vwc, root_depth, eff, lf)
    cec = st.lab.get("cec_meq")
    soil_t = st.r("soil_temp_upper")
    hot = soil_t is not None and soil_t > 32
    sandy = (cec is not None and cec < 8) or st.texture == "desert_sand"
    if crop["slug"] == "strawberry" or sandy or hot:
        pulses = 4
        timing_en = "Short high-frequency pulses — early morning and late afternoon" if hot else "Short high-frequency pulses through the day"
        timing_ar = "نبضات قصيرة متكررة — صباحاً مبكراً وبعد العصر" if hot else "نبضات قصيرة متكررة على مدار اليوم"
    elif cec is not None and cec < 15:
        pulses, timing_en, timing_ar = 2, "Two pulses — morning and early afternoon", "نبضتان — صباحاً وبعد الظهر مبكراً"
    else:
        pulses, timing_en, timing_ar = 1, "One irrigation in the early morning", "رية واحدة صباحاً مبكراً"
    warnings = []
    if halt:
        warnings.append({"en": "Irrigation HALTED: soil is at/above field capacity or waterlogged. Do not irrigate until it drains back to FC.",
                         "ar": "تم إيقاف الري: التربة عند السعة الحقلية أو مشبعة. لا تروِ حتى تصرف."})
    if "DEEP_PERCOLATION" in codes or (st.awc_lower is not None and st.awc_lower >= 90 and not halt):
        warnings.append({"en": "Over-irrigation warning: the lower sensor (B) is near saturation — nitrate is leaching below roots.",
                         "ar": "تحذير ري زائد: الحساس السفلي قرب التشبع — النترات تغسل أسفل الجذور."})
    if salinity_state == "exceeds":
        warnings.append({"en": f"ECe exceeds the {crop['name_en']} limit — fertilizer injection PAUSED; run the leaching cycle first.",
                         "ar": f"الملوحة تتجاوز حد {crop['name_ar']} — تم إيقاف حقن السماد؛ نفّذ دورة الغسيل أولاً."})
    kc = stage_kc(crop, st.context.get("stage") or "vegetative")
    return {
        "texture": st.texture, "fc_pct": st.fc, "pwp_pct": st.pwp,
        "vwc_upper": vwc, "vwc_lower": st.r("vwc_lower"),
        "awc_upper": None if st.awc_upper is None else round(st.awc_upper, 1),
        "awc_lower": None if st.awc_lower is None else round(st.awc_lower, 1),
        "matric_kpa": st.r("matric_kpa"),
        "awc_target": [crop["awc_min"], crop["awc_max"]],
        "tension_target": [crop["tension_min"], crop["tension_max"]],
        "root_depth_m": root_depth, "efficiency": eff,
        "salinity_state": salinity_state,
        "leaching_fraction": round(lf, 3), "leaching_pct": round(lf * 100),
        "net_m3_per_feddan": round(net, 1), "gross_m3_per_feddan": round(gross, 1),
        "pulses_per_day": 0 if halt else pulses,
        "m3_per_pulse": round(gross / pulses, 1) if pulses and not halt else 0.0,
        "timing_en": "—" if halt else timing_en, "timing_ar": "—" if halt else timing_ar,
        "halt": halt, "fertilizer_paused": salinity_state == "exceeds",
        "kc_stage_ext": kc,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Module 3 — stage-based macronutrients & tank split
# ---------------------------------------------------------------------------
def nutrient_targets(crop: dict, stage: str) -> dict:
    base = STAGE_NPK_TARGET_PPM_EXT[stage]
    out = {}
    for n in ("n", "p", "k"):
        m = stage_modifier(crop, stage, n)
        lo, hi = base[n]
        out[n] = (round(lo * m, 1), round(hi * m, 1))
    return out


def macronutrients(st: FieldState, crop: dict, stage: str, irrig: dict) -> dict:
    targets = nutrient_targets(crop, stage)
    n, p, k, calibrated = st.n_p_k()
    measured = {"n": n, "p": p, "k": k}
    wetted = WETTED_FRACTION_EXT.get(st.context.get("irrigation_type", "drip"), 1.0)
    depth = crop["lower_depth_cm"] / 100.0
    rows, correction = [], {}
    for key in ("n", "p", "k"):
        lo, hi = targets[key]
        v = measured[key]
        if v is None:
            status, deficit_ppm = "unknown", 0.0
        elif v < lo:
            status, deficit_ppm = "deficient", (lo + hi) / 2 - v
        elif v > hi:
            status, deficit_ppm = "excess", 0.0
        else:
            status, deficit_ppm = "optimal", 0.0
        kg = f.ppm_to_kg_per_feddan(deficit_ppm, depth, st.bulk_density) * wetted
        correction[key] = kg
        rows.append({"nutrient": key.upper(), "measured_ppm": v, "target_ppm": [lo, hi], "status": status,
                     "deficit_ppm": round(deficit_ppm, 1), "correction_kg_element": round(kg, 1)})

    weekly = dict(STAGE_WEEKLY_KG_EXT[stage])
    for key in ("n", "p", "k"):
        weekly[key] *= stage_modifier(crop, stage, key)
        status = next(r["status"] for r in rows if r["nutrient"] == key.upper())
        if status == "excess":
            weekly[key] *= 0.5
    if crop["ca_high"]:
        weekly["ca"] *= 1.3
    if crop["mg_high"]:
        weekly["mg"] *= 1.3

    ph = st.r("ph")
    water_ph, hco3 = st.lab.get("water_ph"), st.lab.get("water_hco3")
    acidify = (ph is not None and ph > 7.5) or (water_ph is not None and water_ph > 7.0) or (hco3 is not None and hco3 > 1.5)
    soil_t = st.r("soil_temp_upper")
    avoid_nh4 = bool(crop.get("avoid_ammonium_hot_soil")) and soil_t is not None and soil_t > 28

    # Micronutrient chelates per week (external rates, spec forms).
    micro = {}
    if (ph is not None and ph > 7.5) or "fe" in crop["micros"]:
        fe = MICRO_WEEKLY_KG_EXT["fe_eddha"]
        if (ph is not None and ph > 8.0) or (st.lab.get("caco3_pct") or 0) > 10:
            fe *= 2
        micro["fe_eddha"] = fe
    for el, prod in (("zn", "zn_edta"), ("mn", "mn_edta"), ("cu", "cu_edta")):
        if el in crop["micros"]:
            micro[prod] = MICRO_WEEKLY_KG_EXT[prod]
    water_b = st.lab.get("water_boron_ppm")
    boron_skipped = False
    if "b" in crop["micros"]:
        if water_b is not None and water_b > 0.5:
            boron_skipped = True
        else:
            micro["solubor"] = MICRO_WEEKLY_KG_EXT["solubor"]

    common = dict(stage=stage, acidify=acidify, chloride_sensitive=crop["chloride_sensitive"],
                  avoid_ammonium=avoid_nh4, sulfur_crop=crop["s_high"])
    weekly_plan = fertigation.allocate(weekly, micro_kg=micro, **common)
    corr_needs = {"n": correction["n"], "p": correction["p"], "k": correction["k"], "ca": 0.0, "mg": 0.0}
    correction_plan = fertigation.allocate(corr_needs, micro_kg={}, **common) if any(corr_needs.values()) else None

    cec = st.lab.get("cec_meq")
    apps = 7 if (cec is not None and cec < 8) else 4 if (cec is not None and cec < 15) else 2
    apps = max(apps, crop.get("min_fertigations_per_week", 0))
    per_app = {t: [{"product": it["product"], "en": it["en"], "ar": it["ar"], "kg": round(it["kg"] / apps, 3)}
                   for it in items] for t, items in weekly_plan["tanks"].items()}

    notes = [
        {"en": "Tank A (Calcium Nitrate + Fe-EDDHA) and Tank B (phosphates, sulfates, Mg, trace chelates) must never be mixed: Ca + SO4/PO4 precipitates and blocks drippers.",
         "ar": "لا تخلط الخزان A (نترات كالسيوم + حديد EDDHA) مع الخزان B (فوسفات، سلفات، ماغنسيوم، عناصر صغرى): الكالسيوم مع السلفات/الفوسفات يترسب ويسد النقاطات."},
    ]
    if crop["chloride_sensitive"]:
        notes.append({"en": f"KCl is banned for {crop['name_en']} (chloride-sensitive) — potassium supplied as SOP.",
                      "ar": f"كلوريد البوتاسيوم ممنوع لـ {crop['name_ar']} (حساس للكلوريد) — البوتاسيوم من سلفات البوتاسيوم."})
    if boron_skipped:
        notes.append({"en": f"Boron dose skipped: irrigation water already carries {water_b:.2f} ppm B (> 0.5 ppm).",
                      "ar": f"تم إلغاء البورون: مياه الري بها {water_b:.2f} جزء في المليون (> 0.5)."})
    if avoid_nh4:
        notes.append({"en": "Hot soil: ammonium sources avoided for peppers — nitrogen from nitrate forms only.",
                      "ar": "تربة حارة: تم تجنب الأمونيوم للفلفل — النيتروجين من النترات فقط."})
    if irrig["salinity_state"] == "approaching":
        notes.append({"en": "ECe is approaching the crop limit — run the leaching fraction first and keep the fertigation EC low (short, dilute pulses).",
                      "ar": "الملوحة تقترب من حد المحصول — نفّذ نسبة الغسيل أولاً وحافظ على تسميد مخفف بنبضات قصيرة."})
    if irrig["fertilizer_paused"]:
        notes.append({"en": "PAUSED until the leaching cycle brings ECe below the crop limit.",
                      "ar": "متوقف حتى تخفض دورة الغسيل الملوحة تحت حد المحصول."})
    return {
        "stage": stage, "stage_en": STAGE_NAMES[stage]["en"], "stage_ar": STAGE_NAMES[stage]["ar"],
        "npk_label": "Lab-Calibrated" if calibrated else "Unverified Estimate",
        "npk_rows": rows,
        "focus_en": crop["npk_focus_en"], "focus_ar": crop["npk_focus_ar"],
        "weekly_need_kg": {k: round(v, 2) for k, v in weekly.items()},
        "weekly_plan": weekly_plan,
        "correction_plan": correction_plan,
        "applications_per_week": apps,
        "per_application": per_app,
        "paused": irrig["fertilizer_paused"],
        "acidify": acidify,
        "notes": notes,
        "external_note": "Stage N-P-K targets, weekly rates and chelate rates are external references (not in the spec); calibrate with your local extension lab.",
    }


# ---------------------------------------------------------------------------
# Module 4 — chelates, vitamins, biostimulants & biofertilizers
# ---------------------------------------------------------------------------
def biostimulants(st: FieldState, crop: dict, stage: str, alerts: list[dict], npk_rows: list[dict]) -> list[dict]:
    out = []
    ph = st.r("ph")
    air = st.r("air_temp_c")
    vpd = st.vpd
    rh = st.r("rh_pct")
    som = st.lab.get("som_pct")
    cec = st.lab.get("cec_meq")
    codes = {a["rule_code"] for a in alerts}

    def add(key, en, ar, rate_en, rate_ar, why_en, why_ar, source, external=False):
        out.append({"key": key, "en": en, "ar": ar, "rate_en": rate_en, "rate_ar": rate_ar,
                    "reason_en": why_en, "reason_ar": why_ar, "source": source, "external": external})

    if ph is not None and ph > 7.5:
        add("fe_eddha", "Fe-EDDHA 6% ortho-ortho (soil/drip) — mandatory", "حديد EDDHA 6% (أرضي/تنقيط) — إلزامي",
            "In Tank A every fertigation (see weekly programme)", "في الخزان A مع كل تسميد (انظر البرنامج الأسبوعي)",
            f"pH {ph:.1f} > 7.5: inorganic iron oxidises within hours; only EDDHA stays available up to pH 10.",
            f"الحموضة {ph:.1f} > 7.5: الحديد غير المخلبي يتأكسد خلال ساعات.", "Table 2.2 / Section 7.2")
    for el, en, ar in (("zn", "Zn chelate (EDTA / amino)", "زنك مخلبي"), ("mn", "Mn chelate (foliar preferred at high pH)", "منجنيز مخلبي (رش ورقي في الأراضي القلوية)"),
                       ("cu", "Cu-EDTA (small targeted doses)", "نحاس مخلبي (جرعات صغيرة)"), ("b", "Boron (Solubor) — carefully capped", "بورون (سولوبور) — بحذر")):
        if el in crop["micros"]:
            add(el, en, ar, "Tank B (see weekly programme)", "الخزان B (انظر البرنامج الأسبوعي)",
                crop["micro_focus_en"], crop["micro_focus_ar"], "Table 4.3 / Table 2.2")
    if (cec is not None and cec < 10) or (som is not None and som < 2.0) or st.texture in ("desert_sand", "sandy_loam") \
            or "R24_EC_SALINE" in codes:
        add("humic", "Humic & Fulvic Acids (drip)", "أحماض الهيوميك والفولفيك (بالتنقيط)",
            "2–4 kg/feddan per week via drip (external rate)", "2–4 كجم/فدان أسبوعياً بالتنقيط (معدل مرجعي خارجي)",
            "Raises CEC in sandy low-organic soils, stimulates fine roots, chelates locked P/Fe and reduces sodium stress.",
            "يرفع السعة التبادلية في الأراضي الرملية ويحفز الجذور ويخلب الفوسفور والحديد ويقلل إجهاد الصوديوم.",
            "Section 2.3 (rate external)", external=True)
    heat = (air is not None and air > 35) or (vpd is not None and vpd > 1.6) or "CITRUS_KHAMSIN" in codes
    if heat:
        add("ascorbic", "Ascorbic Acid (Vitamin C) foliar", "حمض الأسكوربيك (فيتامين C) رشاً",
            "100–250 ppm foliar spray before/after the heat event", "100–250 جزء في المليون رشاً قبل/بعد موجة الحر",
            f"Heat/VPD stress (air {air} °C, VPD {vpd:.2f} kPa) — neutralises reactive oxygen species." if vpd is not None else "Heat stress — antioxidant protection.",
            "إجهاد حراري — مضاد أكسدة يحمي الخلايا.", "Section 2.3")
        add("seaweed", "Seaweed extract (Ascophyllum nodosum) + free L-amino acids", "مستخلص أعشاب بحرية + أحماض أمينية حرة",
            "Foliar or drip before and after heatwaves / Khamsin (product-label rate)", "رشاً أو بالتنقيط قبل وبعد موجات الحر (حسب الملصق)",
            "Cytokinins, auxins and glycine betaine protect against heatwave (> 36 °C) and Khamsin stress.",
            "سيتوكينينات وأوكسينات وجلايسين بيتاين تحمي من الحر والخماسين.", "Section 2.3")
    if stage == "establishment" or "R24_WATERLOG" in codes or "PEPPER_PHYTO" in codes:
        add("trichoderma", "B-Vitamins (B1, B3, B6) + Trichoderma harzianum drench", "فيتامينات B + ترايكوديرما",
            "Light root drench at transplanting or once soil drains to FC after waterlogging", "إضافة خفيفة للجذور عند الشتل أو بعد صرف التشبع",
            "Accelerates new root hairs and suppresses root-rot fungi.", "يسرع تكوين الشعيرات الجذرية ويقاوم فطريات العفن.",
            "Section 2.3 / Table 2.4")
    if heat or (rh is not None and rh > 70) or crop["slug"] in ("cucumber", "mango"):
        add("silicon", "Salicylic acid / Potassium silicate", "حمض السالسيليك / سيليكات البوتاسيوم",
            "Foliar spray during heat or mildew-risk windows (product-label rate)", "رش ورقي أثناء الحر أو خطر البياض (حسب الملصق)",
            "Reinforces cell walls, activates Systemic Acquired Resistance, cuts transpiration loss.",
            "يقوي جدر الخلايا وينشط المقاومة المكتسبة ويقلل فقد النتح.", "Section 2.3")
    p_row = next((r for r in npk_rows if r["nutrient"] == "P"), None)
    if (ph is not None and ph > 7.5) or (p_row and p_row["status"] == "deficient"):
        add("bacillus_amf", "Bacillus megaterium + Arbuscular Mycorrhizal Fungi (AMF)", "باسيلس ميجاتيريوم + فطريات الميكوريزا",
            "Inoculate via drip at planting / start of season (product-label rate)", "تلقيح بالتنقيط عند الزراعة (حسب الملصق)",
            "Solubilises locked phosphorus and expands root absorption of P, Zn and water.",
            "يذيب الفوسفور المثبت ويوسع امتصاص الجذور للفوسفور والزنك والماء.", "Section 2.3 / Section 7.2")
    if som is not None and som < 1.0:
        add("azotobacter", "Azotobacter / Azospirillum (free-living N-fixers)", "أزوتوباكتر / أزوسبيريلم (مثبتات نيتروجين)",
            "Inoculate with compost at planting (product-label rate)", "تلقيح مع الكمبوست عند الزراعة (حسب الملصق)",
            f"SOM {som:.2f}% — turns inert sand into living, fertile soil.", f"المادة العضوية {som:.2f}% — يحول الرمل الخامل إلى تربة حية.",
            "Section 2.3")
    return out


# ---------------------------------------------------------------------------
# Property gap table
# ---------------------------------------------------------------------------
def gap_table(st: FieldState, crop: dict) -> list[dict]:
    rows = []

    def row(key, en, ar, value, lo, hi, unit, nd=1):
        if value is None:
            status = "unknown"
        elif lo is not None and value < lo:
            status = "deficient"
        elif hi is not None and value > hi:
            status = "excess"
        else:
            status = "optimal"
        tgt = (f"{lo}–{hi}" if lo is not None and hi is not None else f"≤ {hi}" if hi is not None else f"≥ {lo}")
        rows.append({"key": key, "en": en, "ar": ar, "value": None if value is None else round(value, nd),
                     "target": tgt, "unit": unit, "status": status})

    lab = st.lab
    row("ph", "Soil pH", "حموضة التربة", st.r("ph"), crop["ph_min"], crop["ph_max"], "", 1)
    row("ece", "Root-zone ECe (25 °C)", "ملوحة منطقة الجذور", st.ece, None, crop["ec_limit"], "dS/m", 2)
    row("awc", "Available water (upper)", "الماء الميسر (علوي)", st.awc_upper, crop["awc_min"], crop["awc_max"], "%", 0)
    row("tension", "Soil tension", "الشد الرطوبي", st.r("matric_kpa"), crop["tension_min"], crop["tension_max"], "kPa", 0)
    row("soil_temp", "Soil temperature", "حرارة التربة", st.r("soil_temp_upper"), 18, 26, "°C", 1)
    row("orp", "Redox (ORP)", "جهد الأكسدة", st.r("orp_mv"), 300, 600, "mV", 0)
    row("o2", "Soil O2", "أكسجين التربة", st.r("o2_pct"), 12, None, "%", 1)
    row("vpd", "VPD", "عجز ضغط البخار", st.vpd, 0.8, 1.5, "kPa", 2)
    row("som", "Organic matter", "المادة العضوية", lab.get("som_pct"), 2.0, 4.0, "%", 2)
    row("cec", "CEC", "السعة التبادلية", lab.get("cec_meq"), 15, 30, "meq/100g", 1)
    row("caco3", "Active CaCO3", "الجير النشط", lab.get("caco3_pct"), None, 5, "%", 1)
    row("esp", "ESP", "الصوديوم المتبادل", st.esp, None, 10, "%", 1)
    row("sar", "SAR", "نسبة ادمصاص الصوديوم", lab.get("sar"), None, 6, "", 1)
    row("ecw", "Irrigation water ECw", "ملوحة مياه الري", lab.get("water_ec_w"), None, 1.2, "dS/m", 2)
    row("water_b", "Water boron", "بورون المياه", lab.get("water_boron_ppm"), None, 0.5, "ppm", 2)
    row("water_ph", "Water pH", "حموضة المياه", lab.get("water_ph"), 6.0, 7.0, "", 1)
    return rows


# ---------------------------------------------------------------------------
def build(st: FieldState, crop_slug: str, stage: str) -> dict:
    crop = CROP_BY_SLUG[crop_slug]
    st.context = {**st.context, "crop_slug": crop_slug, "stage": stage}
    alerts = alert_engine.evaluate(st, crop_slug)
    irrig = irrigation(st, crop, alerts)
    macro = macronutrients(st, crop, stage, irrig)
    from .pipeline import health_index  # local import avoids a cycle
    shi = health_index(st, crop)
    return {
        "crop": {"slug": crop["slug"], "name_en": crop["name_en"], "name_ar": crop["name_ar"]},
        "stage": stage, "stage_en": STAGE_NAMES[stage]["en"], "stage_ar": STAGE_NAMES[stage]["ar"],
        "soil_health_index": shi,
        "status": alert_engine.overall_status(alerts),
        "gaps": gap_table(st, crop),
        "conditioning": conditioning(st, crop),
        "irrigation": irrig,
        "macronutrients": macro,
        "biostimulants": biostimulants(st, crop, stage, alerts, macro["npk_rows"]),
        "alerts": alerts,
        "advisory_only_note_en": "Advisory only — this system never switches valves, pumps or dosing hardware.",
        "advisory_only_note_ar": "استشاري فقط — النظام لا يتحكم في المحابس أو المضخات أو أجهزة الحقن.",
    }
