"""Tank A / Tank B / Acid tank allocation and chemical-compatibility guard.

Spec rules (Sections 2.1 and 7.2 module 3):
  * Tank A — Calcium Nitrate + Fe-EDDHA (nitrates only)
  * Tank B — phosphates, sulfates, Mg and trace chelates
  * Acid tank — phosphoric / nitric acid
  * Never mix Ca with sulfates or phosphates in the same tank.
  * KCl banned for chloride-sensitive crops (Potatoes, Strawberries).
"""

from __future__ import annotations

from ..knowledge.soil import FERTILIZERS


class TankCompatibilityError(ValueError):
    pass


def validate_tanks(tanks: dict[str, list[dict]], *, chloride_sensitive: bool) -> list[str]:
    """Raise TankCompatibilityError on any unsafe mix. Returns [] when safe."""
    for tank, items in tanks.items():
        contains = set()
        for it in items:
            prod = FERTILIZERS[it["product"]]
            if prod["tank"] != tank:
                raise TankCompatibilityError(f"{it['product']} belongs in tank {prod['tank']}, not {tank}")
            contains.update(prod["contains"])
            if it["product"] == "potassium_chloride" and chloride_sensitive:
                raise TankCompatibilityError("KCl is banned on chloride-sensitive crops")
        if "calcium" in contains and ({"sulfate", "phosphate"} & contains):
            raise TankCompatibilityError(f"Tank {tank}: calcium mixed with sulfate/phosphate (precipitates)")
    return []


def _add(tanks, product, kg):
    if kg <= 0.0005:
        return
    tank = FERTILIZERS[product]["tank"]
    for it in tanks[tank]:
        if it["product"] == product:
            it["kg"] += kg
            return
    tanks[tank].append({"product": product, "kg": kg})


def allocate(needs: dict, *, stage: str, acidify: bool, chloride_sensitive: bool,
             avoid_ammonium: bool, sulfur_crop: bool, micro_kg: dict) -> dict:
    """needs: kg of elemental N, P, K, Ca, Mg per feddan for the period.
    Returns {"tanks": {...}, "supplied": {...}} with products in kg/feddan."""
    tanks: dict[str, list[dict]] = {"A": [], "B": [], "ACID": []}
    need = {k: max(0.0, needs.get(k, 0.0)) for k in ("n", "p", "k", "ca", "mg")}
    supplied = {k: 0.0 for k in ("n", "p", "k", "ca", "mg", "s")}

    def give(product, kg):
        _add(tanks, product, kg)
        prod = FERTILIZERS[product]
        for el in supplied:
            supplied[el] += kg * prod.get(el, 0.0)

    # 1. Calcium (and part of N) via calcium nitrate — Tank A.
    if need["ca"] > 0:
        give("calcium_nitrate", need["ca"] / FERTILIZERS["calcium_nitrate"]["ca"])

    # 2. Phosphorus — acid tank first when acidifying, then MAP/MKP in Tank B.
    p_left = need["p"]
    if acidify and p_left > 0:
        p_acid = p_left * 0.5
        give("phosphoric_acid", p_acid / FERTILIZERS["phosphoric_acid"]["p"])
        p_left -= p_acid
    if p_left > 0:
        prod = "map" if stage in ("establishment", "vegetative") else "mkp"
        give(prod, p_left / FERTILIZERS[prod]["p"])

    # 3. Potassium — SOP (chloride-free) by default; part KNO3 in vegetative stage
    #    when N is still needed and the crop is not an S-focus crop.
    k_left = max(0.0, need["k"] - supplied["k"])
    if k_left > 0:
        n_gap = max(0.0, need["n"] - supplied["n"])
        if stage == "vegetative" and n_gap > 0 and not sulfur_crop:
            k_kno3 = min(k_left * 0.5, n_gap / FERTILIZERS["potassium_nitrate"]["n"] * FERTILIZERS["potassium_nitrate"]["k"])
            give("potassium_nitrate", k_kno3 / FERTILIZERS["potassium_nitrate"]["k"])
            k_left -= k_kno3
        give("sop", k_left / FERTILIZERS["sop"]["k"])

    # 4. Magnesium — MgSO4, Tank B.
    if need["mg"] > 0:
        give("mgso4", need["mg"] / FERTILIZERS["mgso4"]["mg"])

    # 5. Remaining nitrogen.
    n_left = max(0.0, need["n"] - supplied["n"])
    if n_left > 0:
        if not avoid_ammonium:
            give("ammonium_sulfate", n_left / FERTILIZERS["ammonium_sulfate"]["n"])
        else:
            give("calcium_nitrate", n_left / FERTILIZERS["calcium_nitrate"]["n"])

    # 6. Chelated micronutrients.
    for product, kg in micro_kg.items():
        give(product, kg)

    for items in tanks.values():
        for it in items:
            it["kg"] = round(it["kg"], 2)
            it["en"] = FERTILIZERS[it["product"]]["en"]
            it["ar"] = FERTILIZERS[it["product"]]["ar"]
    validate_tanks(tanks, chloride_sensitive=chloride_sensitive)
    return {"tanks": tanks, "supplied": {k: round(v, 2) for k, v in supplied.items()}}
