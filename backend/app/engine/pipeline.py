"""Pure end-to-end pipeline used by the API, the simulator and the tests."""

from __future__ import annotations

from ..knowledge.soil import TEXTURES
from ..services.simulator import build_payload
from . import alerts as alert_engine
from . import formulas as f
from . import telemetry
from .state import FieldState


def process_payload(payload: dict, lab: dict, history: list[dict] | None = None,
                    npk_calibration: dict | None = None) -> dict:
    texture = lab.get("texture_class") if lab.get("texture_class") in TEXTURES else "loam"
    reading = telemetry.flatten(payload)
    reading = telemetry.validate(reading, history)
    t = TEXTURES[texture]
    return telemetry.derive(reading, texture_fc_pwp=(t["fc"], t["pwp"]), npk_calibration=npk_calibration)


def state_from_bundle(bundle: dict, crop_slug: str | None = None, stage: str | None = None) -> FieldState:
    """Build a FieldState straight from a simulator bundle (no database)."""
    payload = build_payload(bundle["sensors"], bundle["fillers"], device_id="SIM", farm_id="SIM", zone_id="SIM")
    reading = process_payload(payload, bundle["lab"])
    ctx = dict(bundle["context"])
    ctx["crop_slug"], ctx["stage"] = crop_slug, stage
    return FieldState(reading=reading, lab=bundle["lab"], context=ctx)


def health_index(st: FieldState, crop: dict | None) -> dict:
    return f.soil_health_index(
        ph=st.r("ph"), ece=st.ece, ece_limit=crop["ec_limit"] if crop else alert_engine.GENERAL_EC_LIMIT,
        awc=st.awc_upper, matric_kpa=st.r("matric_kpa"), orp_mv=st.r("orp_mv"),
        soil_temp_c=st.r("soil_temp_upper"), som_pct=st.lab.get("som_pct"), cec_meq=st.lab.get("cec_meq"),
        ph_window=(crop["ph_min"], crop["ph_max"]) if crop else (6.0, 7.0),
        awc_window=(crop["awc_min"], crop["awc_max"]) if crop else (60.0, 80.0),
        tension_window=(crop["tension_min"], crop["tension_max"]) if crop else (10.0, 35.0),
    )
