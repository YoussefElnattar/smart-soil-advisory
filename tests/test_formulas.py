"""(a) The six Section 7.3 formulas."""
import math

import pytest

from app.engine import formulas as f
from app.knowledge.test_cases import TEST_CASES


@pytest.mark.parametrize("case", [c for c in TEST_CASES if c["spec_vpd_kpa"]], ids=lambda c: c["id"])
def test_vpd_tetens_matches_spec_cases(case):
    s = case["sensors"]
    assert f.vpd_kpa(s["air_temp_c"], s["rh_pct"]) == pytest.approx(case["spec_vpd_kpa"], abs=0.03)


def test_vpd_formula_exact():
    es = 0.6108 * math.exp(17.27 * 30 / (30 + 237.3))
    assert f.saturation_vapor_pressure(30) == pytest.approx(es)
    assert f.vpd_kpa(30, 100) == pytest.approx(0.0)
    assert f.vpd_kpa(30, 0) == pytest.approx(es)


def test_ec25_atc():
    assert f.ec25(2.0, 25.0) == pytest.approx(2.0)
    assert f.ec25(2.0, 35.0) == pytest.approx(2.0 / 1.19)
    assert f.ec25(2.0, 15.0) == pytest.approx(2.0 / 0.81)
    assert f.ec25(f.ec_raw_from_ec25(2.85, 33.4), 33.4) == pytest.approx(2.85)


def test_awc_texture_mapping_and_clamp():
    assert f.awc_pct(45, 40, 22) == 100.0          # above FC clamps
    assert f.awc_pct(20, 40, 22) == 0.0            # below PWP clamps
    assert f.awc_pct(31, 40, 22) == pytest.approx(50.0)
    assert f.awc_for_texture(14.0, "sandy_loam") == pytest.approx(50.0)   # FC 20 / PWP 8 (spec 6.4)
    assert f.awc_for_texture(9.0, "desert_sand") == pytest.approx(50.0)   # FC 13 / PWP 5


def test_leaching_requirement_fao29_and_caps():
    assert f.leaching_requirement(1.0, 2.5) == pytest.approx(1.0 / (12.5 - 1.0))
    assert f.leaching_requirement(0.1, 3.5) == f.LR_MIN          # capped at 0.05
    assert f.leaching_requirement(3.0, 1.0) == f.LR_MAX          # capped at 0.40


def test_gross_irrigation_volume():
    # ((20 - 14)/100 × 0.35 × 4200) / (0.9 × (1 - 0.1))
    expected = (0.06 * 0.35 * 4200) / (0.9 * 0.9)
    assert f.gross_irrigation_m3_per_feddan(20, 14, 0.35, 0.9, 0.1) == pytest.approx(expected)
    assert f.gross_irrigation_m3_per_feddan(20, 25, 0.35, 0.9, 0.0) == 0.0


def test_soil_health_index_weights_and_range():
    perfect = f.soil_health_index(ph=6.5, ece=1.0, ece_limit=2.0, awc=70, matric_kpa=20, orp_mv=450,
                                  soil_temp_c=22, som_pct=3.0, cec_meq=20)
    assert perfect["index"] == pytest.approx(100.0)
    bad = f.soil_health_index(ph=9.5, ece=6.0, ece_limit=2.0, awc=0, matric_kpa=150, orp_mv=50,
                              soil_temp_c=45, som_pct=0.1, cec_meq=2)
    assert 0 <= bad["index"] < 15
    assert sum(f.SHI_WEIGHTS.values()) == pytest.approx(1.0)
    partial = f.soil_health_index(ph=6.5, ece=None, ece_limit=2.0, awc=None, matric_kpa=None, orp_mv=None,
                                  soil_temp_c=None, som_pct=None, cec_meq=None)
    assert partial["index"] == pytest.approx(100.0)   # missing probes never drag the index down


def test_spec_range_interpolations():
    assert f.elemental_sulfur_kg_per_feddan(8.2) == 400     # spec Case R1
    assert f.elemental_sulfur_kg_per_feddan(7.6) == 300
    assert f.elemental_sulfur_kg_per_feddan(9.0) == 500
    assert f.compost_m3_per_feddan(0.35) == 30
    assert f.compost_m3_per_feddan(2.5) == 0
    assert 15 <= f.compost_m3_per_feddan(1.6) <= 30
