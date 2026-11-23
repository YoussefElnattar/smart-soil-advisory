"""(c) The five Table 2.4 remediation rules and (d) crop-specific rules for all 10 crops."""
import pytest

from app.engine.alerts import evaluate
from app.knowledge.crops import CROPS


def codes(state, crop=None):
    return {a["rule_code"] for a in evaluate(state, crop)}


# ------------------------------------------------------------------ Table 2.4
def test_healthy_case_has_no_remediation_alerts(mk):
    assert not {c for c in codes(mk()) if c.startswith("R24_")}


def test_rule_ph_alkaline(mk):
    assert "R24_PH_ALKALINE" in codes(mk({"ph": 8.1}))
    assert "R24_PH_ALKALINE" not in codes(mk({"ph": 7.7}))


def test_rule_ph_alkaline_needs_persistence(mk):
    st = mk({"ph": 8.1})
    st.history = [{"ph": 7.2}, {"ph": 7.1}]       # pH only just jumped: not persistent yet
    assert "R24_PH_ALKALINE" not in codes(st)
    st.history = [{"ph": 8.0}, {"ph": 8.2}]
    assert "R24_PH_ALKALINE" in codes(st)


def test_rule_ec_above_crop_threshold_with_adequate_moisture(mk):
    st = mk({"ece": 1.4}, crop="strawberry")      # R3 AWC ~79 % = adequate moisture
    assert "R24_EC_SALINE" in codes(st, "strawberry")
    assert "R24_EC_SALINE" not in codes(mk({"ece": 1.4}, crop="tomato"), "tomato")
    dry = mk({"ece": 1.4, "vwc_upper": 10.0}, crop="strawberry")
    assert "R24_EC_SALINE" not in codes(dry, "strawberry")
    assert "EC_ABOVE_RANGE" in codes(dry, "strawberry")


def test_rule_drought_plus_heat(mk):
    assert "R24_DROUGHT_HEAT" in codes(mk({"vwc_upper": 11.0, "soil_temp_c": 33.5}))
    assert "R24_DROUGHT_HEAT" not in codes(mk({"vwc_upper": 11.0, "soil_temp_c": 30.0}))
    assert "R24_DROUGHT_HEAT" not in codes(mk({"vwc_upper": 18.0, "soil_temp_c": 33.5}))


def test_rule_waterlogging_hypoxia(mk):
    assert "R24_WATERLOG" in codes(mk({"vwc_upper": 20.5, "orp_mv": 150}))
    assert "R24_WATERLOG" not in codes(mk({"vwc_upper": 20.5, "orp_mv": 320}))
    assert "R24_WATERLOG" not in codes(mk({"vwc_upper": 14.0, "orp_mv": 150}))


def test_rule_high_vpd_normal_moisture(mk):
    hot_dry = {"air_temp_c": 34.0, "rh_pct": 40.0}          # VPD ~3.2 kPa
    assert "R24_HIGH_VPD" in codes(mk({**hot_dry, "vwc_upper": 16.0}))     # AWC ~67 %
    assert "R24_HIGH_VPD" not in codes(mk({**hot_dry, "vwc_upper": 11.0}))  # soil not "normal"
    assert "R24_HIGH_VPD" not in codes(mk({"air_temp_c": 22.0, "rh_pct": 65.0, "vwc_upper": 16.0}))


def test_spec_case_r2_waterlogging_and_fungal(mk):
    st = mk(base="R2")
    assert {"R24_WATERLOG", "FUNGAL_RH"} <= codes(st)
    assert next(a for a in evaluate(st) if a["rule_code"] == "R24_WATERLOG")["severity"] == "red"


def test_alerts_are_bilingual(mk):
    for a in evaluate(mk({"ph": 8.3, "vwc_upper": 11, "soil_temp_c": 34}), "tomato"):
        assert a["message_en"] and a["message_ar"] and a["action_en"] and a["action_ar"]
        assert a["severity"] in {"green", "amber", "red"}


# ------------------------------------------------------------ Table 4.3 rules
CROP_TRIGGERS = {
    "tomato": ({"air_temp_c": 34, "rh_pct": 40}, {}, "TOMATO_BER"),
    "potato": ({"matric_kpa": 24, "soil_temp_c": 27.5}, {}, "POTATO_HEAT"),
    "strawberry": ({"ece": 1.3, "rh_pct": 85}, {}, "STRAW_SALINITY"),
    "citrus": ({"air_temp_c": 40, "rh_pct": 20}, {"month": 5}, "CITRUS_KHAMSIN"),
    "grapes": ({"rh_pct": 78}, {}, "GRAPE_MILDEW"),
    "mango": ({"air_temp_c": 3.0}, {"month": 1}, "MANGO_FROST"),
    "pepper": ({"vwc_upper": 19.9, "matric_kpa": 8, "orp_mv": 230}, {}, "PEPPER_PHYTO"),
    "cucumber": ({"soil_temp_c": 16.0}, {}, "CUKE_COLD_SOIL"),
    "onion": ({"ece": 1.5}, {}, "ONION_SALINITY"),
    "pomegranate": ({"matric_kpa": 44}, {"month": 8}, "POM_BAND"),
}


@pytest.mark.parametrize("crop", [c["slug"] for c in CROPS])
def test_crop_specific_rule_fires(mk, crop):
    sensors, ctx, code = CROP_TRIGGERS[crop]
    st = mk(sensors, context=ctx, crop=crop)
    assert code in codes(st, crop)


@pytest.mark.parametrize("crop", [c["slug"] for c in CROPS])
def test_crop_specific_rule_quiet_when_healthy(mk, crop):
    _, ctx, code = CROP_TRIGGERS[crop]
    healthy = {"matric_kpa": 28} if crop == "pomegranate" else {}   # inside its 20–35 kPa band
    assert code not in codes(mk(healthy, context=ctx, crop=crop), crop)


def test_extra_crop_rules(mk):
    assert "POTATO_IRRIGATE" in codes(mk({"matric_kpa": 23}, crop="potato"), "potato")
    assert "STRAW_BOTRYTIS" in codes(mk({"rh_pct": 85}, crop="strawberry"), "strawberry")
    assert "CUKE_DEW" in codes(mk({"air_temp_c": 20, "rh_pct": 95}, crop="cucumber"), "cucumber")
    assert "MANGO_MILDEW" in codes(mk({"rh_pct": 80}, context={"month": 3}, crop="mango"), "mango")
    assert "ONION_DRYDOWN" in codes(mk(crop="onion", stage="ripening"), "onion")
    assert "GRAPE_CHILL" in codes(mk(context={"month": 2, "chill_hours": 230}, crop="grapes"), "grapes")
