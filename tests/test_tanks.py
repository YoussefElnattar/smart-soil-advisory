"""(b) Tank A / B / Acid chemical-incompatibility protection."""
import pytest

from app.engine import fertigation
from app.engine.fertigation import TankCompatibilityError, validate_tanks
from app.knowledge.soil import FERTILIZERS


def _assert_safe(plan):
    for tank, items in plan["tanks"].items():
        contains = set()
        for it in items:
            assert FERTILIZERS[it["product"]]["tank"] == tank
            contains.update(FERTILIZERS[it["product"]]["contains"])
            assert it["product"] != "potassium_chloride"
        assert not ("calcium" in contains and contains & {"sulfate", "phosphate"}), tank


@pytest.mark.parametrize("stage", ["establishment", "vegetative", "flowering", "ripening"])
@pytest.mark.parametrize("acidify", [True, False])
def test_allocation_never_mixes_calcium_with_sulfate_or_phosphate(stage, acidify):
    plan = fertigation.allocate({"n": 6, "p": 3, "k": 8, "ca": 4, "mg": 1.5}, stage=stage, acidify=acidify,
                                chloride_sensitive=True, avoid_ammonium=False, sulfur_crop=False,
                                micro_kg={"fe_eddha": 1, "zn_edta": .25, "solubor": .25})
    _assert_safe(plan)
    names_a = {i["product"] for i in plan["tanks"]["A"]}
    assert "calcium_nitrate" in names_a and "fe_eddha" in names_a
    if acidify:
        assert plan["tanks"]["ACID"]


def test_nutrients_are_delivered():
    plan = fertigation.allocate({"n": 5, "p": 2, "k": 6, "ca": 3, "mg": 1}, stage="flowering", acidify=False,
                                chloride_sensitive=False, avoid_ammonium=False, sulfur_crop=False, micro_kg={})
    s = plan["supplied"]
    for el, need in {"n": 5, "p": 2, "k": 6, "ca": 3, "mg": 1}.items():
        assert s[el] >= need - 0.05, el


def test_validator_rejects_calcium_with_sulfate():
    bad = {"A": [{"product": "calcium_nitrate", "kg": 5}], "B": [], "ACID": []}
    bad["A"].append({"product": "sop", "kg": 2})
    with pytest.raises(TankCompatibilityError):
        validate_tanks(bad, chloride_sensitive=False)


def test_validator_rejects_calcium_with_phosphate_even_if_mislabeled_tank():
    bad = {"A": [], "B": [{"product": "calcium_nitrate", "kg": 5}, {"product": "map", "kg": 2}], "ACID": []}
    with pytest.raises(TankCompatibilityError):
        validate_tanks(bad, chloride_sensitive=False)


def test_kcl_banned_on_chloride_sensitive_crops():
    tanks = {"A": [], "B": [{"product": "potassium_chloride", "kg": 3}], "ACID": []}
    with pytest.raises(TankCompatibilityError):
        validate_tanks(tanks, chloride_sensitive=True)
    assert validate_tanks(tanks, chloride_sensitive=False) == []


def test_pepper_hot_soil_avoids_ammonium():
    plan = fertigation.allocate({"n": 8, "p": 1, "k": 2, "ca": 0.5, "mg": 0}, stage="vegetative", acidify=False,
                                chloride_sensitive=False, avoid_ammonium=True, sulfur_crop=False, micro_kg={})
    prods = {i["product"] for t in plan["tanks"].values() for i in t}
    assert "ammonium_sulfate" not in prods
