"""Advisory alert engine (advisory only — never emits actuator commands).

Sources: Table 2.4 (5 remediation rules), Table 4.3 + Section 7.2 module 5
(crop-specific rules), Section 3 (dual-depth over-irrigation) and Section 6.4
(hardware faults). Each alert is bilingual.
"""

from __future__ import annotations

from ..knowledge.crops import CROP_BY_SLUG
from .state import FieldState

SEVERITY_ORDER = {"green": 0, "amber": 1, "red": 2}
GENERAL_EC_LIMIT = 2.0  # Table 1.1 general ECe range 0.8–2.0 dS/m when no crop is active


def _a(code, severity, source, en, ar, action_en, action_ar):
    return {"rule_code": code, "severity": severity, "source": source,
            "message_en": en, "message_ar": ar,
            "action_en": action_en, "action_ar": action_ar}


def _fmt(v, nd=1):
    return "—" if v is None else f"{v:.{nd}f}"


def evaluate(state: FieldState, crop_slug: str | None = None) -> list[dict]:
    alerts: list[dict] = []
    crop = CROP_BY_SLUG.get(crop_slug) if crop_slug else None
    ph = state.r("ph")
    ece = state.ece
    awc = state.awc_upper
    soil_t = state.r("soil_temp_upper")
    orp = state.r("orp_mv")
    vpd = state.vpd
    rh = state.r("rh_pct")
    air = state.r("air_temp_c")
    matric = state.r("matric_kpa")
    ec_limit = crop["ec_limit"] if crop else GENERAL_EC_LIMIT

    # ---------------- Table 2.4 — five remediation rules -------------------
    if ph is not None and ph > 7.8:
        recent = [h.get("ph") for h in state.history[:2] if h.get("ph") is not None]
        if all(p > 7.8 for p in recent):
            alerts.append(_a(
                "R24_PH_ALKALINE", "amber", "Table 2.4",
                f"Soil pH {ph:.1f} is persistently above 7.8 — alkaline phosphorus & micronutrient lockout.",
                f"حموضة التربة {ph:.1f} أعلى من 7.8 باستمرار — انغلاق الفوسفور والعناصر الصغرى.",
                "Pre-plant: incorporate elemental sulfur (300–500 kg/feddan) + matured compost. In-season: inject phosphoric/nitric/sulfuric acid to bring irrigation water to pH 5.8–6.2; switch Fe to Fe-EDDHA.",
                "قبل الزراعة: أضف كبريت زراعي (300–500 كجم/فدان) + كمبوست ناضج. أثناء الموسم: احقن حمض فوسفوريك/نيتريك/كبريتيك لضبط ماء الري على 5.8–6.2؛ استخدم حديد EDDHA."))

    if ece is not None and awc is not None and ece > ec_limit and awc >= 60:
        alerts.append(_a(
            "R24_EC_SALINE", "red", "Table 2.4",
            f"Root-zone ECe {ece:.2f} dS/m exceeds the {'crop' if crop else 'general'} limit of {ec_limit:.1f} dS/m with adequate moisture (AWC {awc:.0f}%) — salt accumulation.",
            f"ملوحة منطقة الجذور {ece:.2f} ديسيسيمنز/م تتجاوز الحد {ec_limit:.1f} مع رطوبة كافية ({awc:.0f}%) — تراكم أملاح.",
            "Pause fertilizer injection; run a leaching cycle (15–25% extra water above FC); apply liquid calcium + humic/carboxylic salinity reducers, or gypsum if Na+ is high.",
            "أوقف حقن السماد؛ نفّذ دورة غسيل (15–25% ماء إضافي فوق السعة الحقلية)؛ أضف كالسيوم سائل + محسنات ملوحة هيومية، أو جبس إذا كان الصوديوم مرتفعاً."))

    elif ece is not None and ece > ec_limit:
        alerts.append(_a(
            "EC_ABOVE_RANGE", "amber", "Table 1.1 / Table 4.1",
            f"Root-zone ECe {ece:.2f} dS/m is above the {'crop' if crop else 'general'} limit of {ec_limit:.1f} dS/m (soil is dry, so salts are concentrated — re-check after irrigation).",
            f"ملوحة منطقة الجذور {ece:.2f} أعلى من الحد {ec_limit:.1f} (التربة جافة فتتركز الأملاح — أعد القياس بعد الري).",
            "Irrigate to field capacity with the best-quality water available, then re-measure; if ECe stays high, run a leaching cycle.",
            "اروِ حتى السعة الحقلية بأفضل مياه متاحة ثم أعد القياس؛ إن بقيت الملوحة مرتفعة نفّذ دورة غسيل."))

    if awc is not None and soil_t is not None and awc < 60 and soil_t > 32:
        alerts.append(_a(
            "R24_DROUGHT_HEAT", "red", "Table 2.4",
            f"Low soil moisture (AWC {awc:.0f}%) with soil temperature {soil_t:.1f} °C — combined drought and root heat stress.",
            f"رطوبة منخفضة ({awc:.0f}%) مع حرارة تربة {soil_t:.1f} °م — إجهاد جفاف وحرارة للجذور.",
            "Switch to short high-frequency pulses early morning and late afternoon; apply straw mulch or white-on-black reflective plastic mulch.",
            "تحوّل إلى نبضات ري قصيرة متكررة صباحاً مبكراً وبعد العصر؛ استخدم غطاء قش أو بلاستيك عاكس أبيض/أسود."))

    if awc is not None and orp is not None and awc > 80 and orp < 200:
        alerts.append(_a(
            "R24_WATERLOG", "red", "Table 2.4",
            f"Waterlogging & root hypoxia: AWC {awc:.0f}% with Redox {orp:.0f} mV (< +200 mV) — root rot risk.",
            f"تشبع مائي ونقص أكسجين الجذور: رطوبة {awc:.0f}% وأكسدة {orp:.0f} مللي فولت (< +200) — خطر عفن الجذور.",
            "Stop irrigation immediately; verify drainage tiles/ditches; reduce pulse duration; once soil drains to FC, drench root zone with Trichoderma + humic acid.",
            "أوقف الري فوراً؛ افحص المصارف؛ قلل مدة النبضات؛ بعد الصرف للسعة الحقلية أضف ترايكوديرما + هيوميك لمنطقة الجذور."))

    if vpd is not None and awc is not None and vpd > 1.8 and 60 <= awc <= 80:
        alerts.append(_a(
            "R24_HIGH_VPD", "amber", "Table 2.4",
            f"VPD {vpd:.2f} kPa (> 1.8) with normal soil moisture — atmospheric demand outpacing root uptake.",
            f"عجز ضغط البخار {vpd:.2f} كيلوباسكال (> 1.8) مع رطوبة تربة طبيعية — الطلب الجوي يفوق امتصاص الجذور.",
            "Increase drip frequency slightly at midday; activate misting/shading if available; foliar seaweed extract + calcium + ascorbic acid to prevent blossom drop.",
            "زد تكرار الري قليلاً وقت الظهيرة؛ فعّل الرذاذ/التظليل إن وجد؛ رش أعشاب بحرية + كالسيوم + فيتامين C لمنع تساقط الأزهار."))

    # ---------------- Fungal humidity window (Sections 1.3, 6.5 R2) ----------
    leaf = state.r("leaf_wetness")
    if (rh is not None and rh > 80) or (leaf is not None and leaf >= 50):
        alerts.append(_a(
            "FUNGAL_RH", "amber", "Section 1.3 / Case R2",
            f"High fungal infection risk: RH {_fmt(rh, 0)}%, leaf wetness {_fmt(leaf, 0)}%.",
            f"خطر إصابة فطرية مرتفع: رطوبة {_fmt(rh, 0)}%، بلل الأوراق {_fmt(leaf, 0)}%.",
            "Ventilate (greenhouse), avoid wetting foliage at dusk; apply preventive fungicide only while the risk window lasts.",
            "هوِّ الصوبة وتجنب بلل الأوراق عند الغروب؛ رش وقائي فقط أثناء فترة الخطر."))

    # ---------------- Dual-depth deep percolation (Section 3) ----------------
    lower_now = state.r("vwc_lower")
    if lower_now is not None and state.history:
        prev = state.history[0].get("vwc_lower")
        awc_low = state.awc_lower
        if prev is not None and lower_now - prev > 2.0 and awc_low is not None and awc_low >= 90:
            alerts.append(_a(
                "DEEP_PERCOLATION", "amber", "Section 3 (dual-depth sensing)",
                f"Lower sensor moisture jumped {lower_now - prev:.1f} points after watering — over-irrigation is washing nitrate below the roots.",
                f"ارتفعت رطوبة الحساس السفلي {lower_now - prev:.1f} نقطة بعد الري — الري الزائد يغسل النترات أسفل الجذور.",
                "Shorten pulse duration and stop irrigating once the upper sensor reaches field capacity.",
                "قصّر مدة النبضة وأوقف الري عند وصول الحساس العلوي للسعة الحقلية."))

    # ---------------- Hardware health (Section 6.4) --------------------------
    faults = state.r("fault_flags") or []
    if faults:
        alerts.append(_a(
            "HW_MAINTENANCE", "amber", "Section 6.4",
            "Hardware Maintenance Alert: " + ", ".join(faults) + ". Affected values were excluded from recommendations.",
            "تنبيه صيانة الأجهزة: " + "، ".join(faults) + ". تم استبعاد القيم المتأثرة من التوصيات.",
            "Inspect, clean and re-seat the affected probe; check cable glands and RS485 wiring.",
            "افحص ونظف وأعد تثبيت الحساس المتأثر؛ راجع جلب الكابلات وأسلاك RS485."))
    batt = state.r("battery_v")
    if batt is not None and batt < 12.0:
        alerts.append(_a(
            "HW_BATTERY_LOW", "amber", "Section 6.2 hardware_health",
            f"Node battery low: {batt:.2f} V (LiFePO4 12.8 V pack).",
            f"بطارية الوحدة منخفضة: {batt:.2f} فولت.",
            "Clean the solar panel and check the MPPT charger.",
            "نظّف اللوح الشمسي وافحص منظم الشحن MPPT."))

    if crop:
        alerts.extend(_crop_rules(state, crop))

    alerts.sort(key=lambda a: -SEVERITY_ORDER[a["severity"]])
    return alerts


def _crop_rules(state: FieldState, crop: dict) -> list[dict]:
    out: list[dict] = []
    slug = crop["slug"]
    name_en, name_ar = crop["name_en"], crop["name_ar"]
    ece, vpd = state.ece, state.vpd
    rh, air = state.r("rh_pct"), state.r("air_temp_c")
    soil_t, matric = state.r("soil_temp_upper"), state.r("matric_kpa")
    orp, awc = state.r("orp_mv"), state.awc_upper
    month = state.month
    src = f"Table 4.3 — {name_en}"

    def add(code, sev, en, ar, act_en, act_ar):
        out.append(_a(code, sev, src, en, ar, act_en, act_ar))

    if slug == "tomato":
        if (vpd is not None and vpd > 1.6) or (ece is not None and ece > 2.5):
            add("TOMATO_BER", "amber",
                f"Tomato Blossom-End Rot risk: VPD {_fmt(vpd, 2)} kPa, ECe {_fmt(ece, 2)} dS/m.",
                f"خطر عفن الطرف الزهري في الطماطم: VPD {_fmt(vpd, 2)}، ECe {_fmt(ece, 2)}.",
                "Boost calcium delivery (calcium nitrate in Tank A + Ca/B foliar) and keep moisture steady.",
                "زد الكالسيوم (نترات كالسيوم في الخزان A + رش كالسيوم/بورون) وثبّت الرطوبة.")
    elif slug == "potato":
        if matric is not None and matric >= 22:
            add("POTATO_IRRIGATE", "amber",
                f"Potato soil tension {matric:.0f} kPa reached the 22 kPa irrigation trigger.",
                f"شد التربة للبطاطس {matric:.0f} كيلوباسكال وصل لحد بدء الري 22.",
                "Irrigate now — potatoes are very sensitive to moisture swings during bulking.",
                "اروِ الآن — البطاطس حساسة جداً لتذبذب الرطوبة أثناء التضخم.")
        if soil_t is not None and soil_t > 26:
            add("POTATO_HEAT", "red" if soil_t > 27 else "amber",
                f"Potato soil temperature {soil_t:.1f} °C exceeds 26 °C — tuber bulking halts above 27 °C.",
                f"حرارة تربة البطاطس {soil_t:.1f} °م تتجاوز 26 — يتوقف تضخم الدرنات فوق 27 °م.",
                "Irrigate in cool hours and mulch to cool the ridge.",
                "اروِ في الساعات الباردة واستخدم غطاء لتبريد الخط.")
    elif slug == "strawberry":
        if ece is not None and ece > 1.0:
            add("STRAW_SALINITY", "red",
                f"Strawberry salinity alarm: ECe {ece:.2f} dS/m > 1.0 dS/m.",
                f"إنذار ملوحة الفراولة: ECe {ece:.2f} > 1.0 ديسيسيمنز/م.",
                "Leach with fresh water and run short drip pulses at 10 cm depth; zero excess Na/Cl.",
                "اغسل بماء عذب ونبضات قصيرة عند 10 سم؛ لا صوديوم/كلوريد زائد.")
        if rh is not None and rh > 80:
            add("STRAW_BOTRYTIS", "amber",
                f"Gray mold (Botrytis) risk: RH {rh:.0f}% > 80%.",
                f"خطر العفن الرمادي: رطوبة {rh:.0f}% > 80%.",
                "Ventilate low tunnels during the day and avoid overhead wetting.",
                "هوِّ الأنفاق نهاراً وتجنب الرش العلوي.")
    elif slug == "citrus":
        if air is not None and air > 38:
            add("CITRUS_KHAMSIN", "red",
                f"Khamsin heat {air:.1f} °C (> 38 °C) — June fruit-drop risk.",
                f"حرارة خماسين {air:.1f} °م (> 38) — خطر تساقط الثمار.",
                "Apply seaweed + ascorbic acid before the hot wind; add cooling irrigation pulses.",
                "رش أعشاب بحرية + فيتامين C قبل الرياح الحارة؛ أضف نبضات ري للتبريد.")
        if vpd is not None and vpd > 1.8 and month in (4, 5, 6):
            add("CITRUS_VPD", "amber",
                f"High VPD {vpd:.2f} kPa during Apr–Jun bloom/set.",
                f"VPD مرتفع {vpd:.2f} أثناء التزهير والعقد.",
                "Schedule short cooling pulses; check 20 cm and 50 cm moisture.",
                "جدول نبضات تبريد قصيرة؛ راجع الرطوبة عند 20 و50 سم.")
    elif slug == "grapes":
        if rh is not None and rh > 70:
            add("GRAPE_MILDEW", "amber",
                f"Grape mildew risk: RH {rh:.0f}% > 70%.",
                f"خطر البياض في العنب: رطوبة {rh:.0f}% > 70%.",
                "Open the canopy for airflow; preventive sulfur/fungicide only during the risk window.",
                "افتح المجموع الخضري للتهوية؛ رش وقائي أثناء فترة الخطر فقط.")
        ch = state.chill_hours
        if ch is not None and month in (12, 1, 2, 3):
            lo = crop["chill_hours"][0]
            add("GRAPE_CHILL", "green" if ch >= lo else "amber",
                f"Winter chilling: {ch:.0f} h accumulated (needs 150–400 h < 7.2 °C).",
                f"ساعات البرودة: {ch:.0f} ساعة (يحتاج 150–400 ساعة < 7.2 °م).",
                "Chill met — expect uniform budbreak." if ch >= lo else "Chill below requirement — consider a budbreak agent per local extension advice.",
                "تحققت البرودة — تفتح منتظم متوقع." if ch >= lo else "البرودة أقل من المطلوب — استشر الإرشاد بشأن منشطات التفتح.")
    elif slug == "mango":
        if air is not None and air < 4:
            add("MANGO_FROST", "red",
                f"Mango frost risk: air {air:.1f} °C approaching < 4 °C.",
                f"خطر صقيع المانجو: الهواء {air:.1f} °م يقترب من < 4.",
                "Irrigate before the cold night and cover young trees.",
                "اروِ قبل الليلة الباردة وغطِّ الأشجار الصغيرة.")
        if rh is not None and rh > 75 and month in (2, 3, 4):
            add("MANGO_MILDEW", "amber",
                f"Flowering-time humidity {rh:.0f}% > 75% — powdery mildew risk.",
                f"رطوبة {rh:.0f}% > 75% وقت التزهير — خطر البياض الدقيقي.",
                "Preventive sulfur/potassium silicate spray on blossoms.",
                "رش وقائي كبريت/سيليكات بوتاسيوم على النورات.")
    elif slug == "pepper":
        high_moist = (awc is not None and awc > crop["awc_max"]) or (matric is not None and matric < crop["tension_min"])
        if high_moist and orp is not None and orp < 250:
            add("PEPPER_PHYTO", "red",
                f"Phytophthora wilt alarm: high moisture + Redox {orp:.0f} mV (< +250 mV).",
                f"إنذار ذبول الفيتوفثورا: رطوبة عالية + أكسدة {orp:.0f} مللي فولت (< +250).",
                "Stop irrigation until the soil drains; drench Trichoderma once aerated.",
                "أوقف الري حتى تصرف التربة؛ أضف ترايكوديرما بعد التهوية.")
    elif slug == "cucumber":
        if soil_t is not None and soil_t < 17:
            add("CUKE_COLD_SOIL", "red" if soil_t < 15 else "amber",
                f"Cucumber soil temperature {soil_t:.1f} °C (< 17 °C alert; < 15 °C causes wilting).",
                f"حرارة تربة الخيار {soil_t:.1f} °م (تنبيه < 17؛ ذبول < 15).",
                "Warm the root zone (mulch/tunnel) and irrigate with warmer water at midday.",
                "دفّئ منطقة الجذور (غطاء/نفق) واروِ بماء أدفأ ظهراً.")
        spread = state.dew_point_spread
        if spread is not None and spread < 2.0:
            add("CUKE_DEW", "amber",
                f"Dew-point spread {spread:.1f} °C — condensation imminent (downy mildew).",
                f"الفرق عن نقطة الندى {spread:.1f} °م — تكثف وشيك (بياض زغبي).",
                "Ventilate the greenhouse now.",
                "هوِّ الصوبة الآن.")
    elif slug == "onion":
        if ece is not None and ece > 1.2:
            add("ONION_SALINITY", "red",
                f"Onion salinity: ECe {ece:.2f} dS/m > 1.2 dS/m.",
                f"ملوحة البصل: ECe {ece:.2f} > 1.2 ديسيسيمنز/م.",
                "Leach and keep shallow 10–20 cm moisture steady.",
                "اغسل التربة وثبّت الرطوبة السطحية 10–20 سم.")
        if state.context.get("stage") == "ripening":
            add("ONION_DRYDOWN", "amber",
                "Onion pre-harvest dry-down: halt irrigation 2–3 weeks before harvest for curing.",
                "تجفيف البصل قبل الحصاد: أوقف الري قبل الحصاد بـ 2–3 أسابيع.",
                "Set the last irrigation date 14–21 days before the planned harvest.",
                "حدد آخر رية قبل الحصاد بـ 14–21 يوماً.")
    elif slug == "pomegranate":
        lo, hi = crop["zero_variance_band"]
        if month in crop["zero_variance_months"] and matric is not None and not (lo <= matric <= hi):
            add("POM_BAND", "red",
                f"Pomegranate zero-variance band broken: tension {matric:.0f} kPa outside 20–35 kPa (Jul–Sep) — fruit splitting risk.",
                f"خروج الرمان عن النطاق الثابت: الشد {matric:.0f} خارج 20–35 كيلوباسكال — خطر تشقق الثمار.",
                "Check for a missed drip cycle and restore regular irrigation immediately.",
                "افحص دورة الري الفائتة وأعد الانتظام فوراً.")
    return out


def overall_status(alerts: list[dict]) -> str:
    if not alerts:
        return "green"
    return max((a["severity"] for a in alerts), key=lambda s: SEVERITY_ORDER[s])
