import os
import sys
from pathlib import Path

os.environ.setdefault("SOIL_DB_PATH", ":memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import copy  # noqa: E402

import pytest  # noqa: E402

from app.engine.pipeline import state_from_bundle  # noqa: E402
from app.services.simulator import case_bundle  # noqa: E402


def make_state(sensors=None, lab=None, context=None, crop=None, stage="vegetative", base="R3"):
    """Start from a healthy spec case (R3) and override selected values."""
    b = copy.deepcopy(case_bundle(base))
    b["sensors"].update(sensors or {})
    b["lab"].update(lab or {})
    b["context"].update(context or {})
    return state_from_bundle(b, crop_slug=crop, stage=stage)


@pytest.fixture
def mk():
    return make_state
