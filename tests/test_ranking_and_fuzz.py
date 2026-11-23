"""(e) 10-crop ranking across the six spec cases and (f) 60 randomized fuzz inputs."""
import math

import pytest

from app.engine.matcher import match_all
from app.engine.pipeline import state_from_bundle
from app.engine.prescription import build
from app.knowledge.crops import CROPS, STAGES
from app.knowledge.soil import FERTILIZERS
from app.knowledge.test_cases import CASE_BY_ID, TEST_CASES
from app.services.simulator import MODES, case_bundle, random_bundle


@pytest.mark.parametrize("case", [c for c in TEST_CASES if c["expected_top"]], ids=lambda c: c["id"])
def test_ranking_matches_spec_expectation(case):
    """#1 crop is one the spec expects, and every expected crop is in the top len(expected)+2."""
    ranking = match_all(state_from_bundle(case_bundle(case["id"])))
    order = [r["slug"] for r in ranking]
    expected = case["expected_top"]
    assert order[0] in expected, f"{case['id']} ranked {order[:4]}"
    window = len(expected) + 2
    for slug in expected:
        assert slug in order[:window], f"{case['id']}: {slug} not in top {window}: {order[:window]}"
    assert len(ranking) == 10 and all(0 <= r["score"] <= 100 for r in ranking)


def test_r3_top_two_ready_to_plant():
    top = match_all(state_from_bundle(case_bundle("R3")))[:2]
    assert {r["slug"] for r in top} == {"strawberry", "potato"}
    assert all(r["tier"] == "ready" for r in top)


def test_r6_top_three_exact():
    top = [r["slug"] for r in match_all(state_from_bundle(case_bundle("R6")))[:3]]
    assert set(top) == {"onion", "potato", "tomato"}


def test_r4_disqualifies_strawberries_and_onions():
    ranking = {r["slug"]: r for r in match_all(state_from_bundle(case_bundle("R4")))}
    for slug in CASE_BY_ID["R4"]["expected_disqualified"]:
        assert ranking[slug]["disqualified"] and ranking[slug]["tier"] == "reclaim"


def test_limiting_factors_explain_low_scores():
    ranking = {r["slug"]: r for r in match_all(state_from_bundle(case_bundle("R1")))}
    texts = " ".join(lim["en"] for lim in ranking["strawberry"]["limiting_factors"])
    assert "ECe" in texts and "pH" in texts


def test_r1_prescription_matches_spec_additions():
    rx = build(state_from_bundle(case_bundle("R1")), "pomegranate", "vegetative")
    cond = {c["key"]: c for c in rx["conditioning"]}
    assert cond["sulfur"]["amount"] == 400
    assert "compost" in cond and "acid_injection" in cond
    assert rx["irrigation"]["leaching_pct"] == 20
    assert {"fe_eddha", "humic", "ascorbic", "seaweed"} <= {b["key"] for b in rx["biostimulants"]}


def test_r2_prescription_halts_irrigation():
    rx = build(state_from_bundle(case_bundle("R2")), "tomato", "vegetative")
    assert rx["irrigation"]["halt"] and rx["irrigation"]["gross_m3_per_feddan"] == 0
    assert "trichoderma" in {b["key"] for b in rx["biostimulants"]}


def test_r3_strawberry_maintenance_tank_split():
    rx = build(state_from_bundle(case_bundle("R3")), "strawberry", "establishment")
    tanks = rx["macronutrients"]["weekly_plan"]["tanks"]
    assert {"calcium_nitrate", "fe_eddha"} <= {i["product"] for i in tanks["A"]}
    assert {"sop", "map", "solubor", "zn_edta"} <= {i["product"] for i in tanks["B"]}


def test_r4_gypsum_and_leaching():
    rx = build(state_from_bundle(case_bundle("R4")), "pomegranate", "flowering")
    cond = {c["key"]: c for c in rx["conditioning"]}
    assert cond["gypsum"]["amount"] > 0
    assert 20 <= rx["irrigation"]["leaching_pct"] <= 25


def test_r6_onion_high_p_sulfur_zinc_copper():
    rx = build(state_from_bundle(case_bundle("R6")), "onion", "establishment")
    prods = {i["product"] for t in rx["macronutrients"]["weekly_plan"]["tanks"].values() for i in t}
    assert {"map", "sop", "zn_edta", "cu_edta"} <= prods
    p_row = next(r for r in rx["macronutrients"]["npk_rows"] if r["nutrient"] == "P")
    assert p_row["status"] == "deficient"


def _finite(obj):
    if isinstance(obj, float):
        assert math.isfinite(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _finite(v)


@pytest.mark.parametrize("seed", range(60))
def test_fuzz_random_inputs_are_safe(seed):
    mode = list(MODES)[seed % len(MODES)]
    st = state_from_bundle(random_bundle(mode, seed))
    assert len(match_all(st)) == 10
    rx = build(st, CROPS[seed % 10]["slug"], STAGES[seed % 4])
    _finite(rx)
    ir = rx["irrigation"]
    assert ir["gross_m3_per_feddan"] >= 0 and 0 <= ir["leaching_fraction"] <= 0.40
    for plan in (rx["macronutrients"]["weekly_plan"], rx["macronutrients"]["correction_plan"]):
        if not plan:
            continue
        for items in plan["tanks"].values():
            contains = set()
            for it in items:
                assert it["kg"] >= 0 and it["product"] != "potassium_chloride"
                contains.update(FERTILIZERS[it["product"]]["contains"])
            assert not ("calcium" in contains and contains & {"sulfate", "phosphate"})
    shi = rx["soil_health_index"]["index"]
    assert shi is None or 0 <= shi <= 100
