"""End-to-end API checks with an in-memory database."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.simulator import build_payload, case_bundle


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client):
    return client.post("/api/v1/devices/EGY-NODE-001/rotate-token").json()["token"]


def _payload(**over):
    b = case_bundle("R3")
    p = build_payload(b["sensors"], b["fillers"], device_id="EGY-NODE-001", farm_id="1", zone_id="1")
    p["soil_upper"].update(over)
    return p


def test_ingest_requires_valid_token(client):
    assert client.post("/api/v1/telemetry/ingest", json=_payload()).status_code == 401
    r = client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Device-Token": "wrong"})
    assert r.status_code == 401


def test_ingest_accepts_spec_contract(client, token):
    r = client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Device-Token": token})
    assert r.status_code == 200 and r.json()["accepted"] and r.json()["advisory_only"]
    dash = client.get("/api/v1/zones/1/dashboard").json()
    assert dash["latest"]["ec25_upper"] == pytest.approx(0.85, abs=0.01)
    assert dash["devices"][0]["status"] == "online"


def test_optional_sensors_may_be_null(client, token):
    p = _payload(o2_pct=None, orp_mv=None)
    p["microclimate"]["leaf_wetness_pct"] = None
    r = client.post("/api/v1/telemetry/ingest", json=p, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_out_of_physics_values_flagged_not_used(client, token):
    r = client.post("/api/v1/telemetry/ingest", json=_payload(ph=14.5, vwc_pct=130), headers={"X-Device-Token": token})
    assert r.status_code == 200
    flags = r.json()["fault_flags"]
    assert any(f.startswith("ph_out_of_range") for f in flags)
    assert any(f.startswith("vwc_upper_out_of_range") for f in flags)
    dash = client.get("/api/v1/zones/1/dashboard").json()
    assert dash["latest"]["ph"] is None
    assert any(a["rule_code"] == "HW_MAINTENANCE" for a in dash["alerts"])


def test_simulator_cases_and_random(client):
    for cid in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        assert client.post("/api/v1/simulator/push", json={"zone_id": 2, "case_id": cid}).status_code == 200
    for mode in ["random", "healthy", "saline", "alkaline", "waterlogged", "heatwave"]:
        r = client.post("/api/v1/simulator/random", json={"zone_id": 2, "mode": mode, "seed": 7})
        assert r.status_code == 200 and r.json()["status"] in {"green", "amber", "red"}


def test_manual_slider_push(client):
    sensors = {"vwc_upper": 18, "vwc_lower": 15, "matric_kpa": 20, "soil_temp_c": 22, "ece": 1.1, "ph": 7.0,
               "n": 40, "p": 20, "k": 150, "orp_mv": 400, "air_temp_c": 25, "rh_pct": 55}
    r = client.post("/api/v1/simulator/push", json={"zone_id": 2, "sensors": sensors,
                                                    "lab": {"texture_class": "loam"}, "context": {"season": "seifi"}})
    assert r.status_code == 200


def test_match_and_prescription_endpoints(client):
    client.post("/api/v1/simulator/push", json={"zone_id": 2, "case_id": "R4"})
    m = client.post("/api/v1/optimize/match-crops", json={"zone_id": 2}).json()
    assert m["ranking"][0]["slug"] == "pomegranate"
    rx = client.post("/api/v1/optimize/prescription", json={"zone_id": 2}).json()
    assert rx["crop"]["slug"] == "pomegranate" and rx["id"]
    assert client.get(f"/api/v1/prescriptions/{rx['id']}").json()["crop"]["slug"] == "pomegranate"


def test_lab_profile_calibrates_npk(client, token):
    client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Device-Token": token})   # raw N = 55
    r = client.put("/api/v1/zones/1/lab-profile", json={"texture_class": "sandy_loam", "lab_n_ppm": 40, "cec_meq": 14})
    assert r.json()["npk_calibration"]["n"]["offset"] == pytest.approx(-15.0)
    client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Device-Token": token})
    latest = client.get("/api/v1/zones/1/dashboard").json()["latest"]
    assert latest["npk_calibrated"] == 1 and latest["n_cal"] == pytest.approx(40.0)


def test_crops_kb_and_filters(client):
    assert len(client.get("/api/v1/crops").json()["crops"]) == 10
    high = client.get("/api/v1/crops?min_ec=2.5").json()["crops"]
    assert {c["slug"] for c in high} == {"tomato", "cucumber", "pomegranate"}
    assert {c["slug"] for c in client.get("/api/v1/crops", params={"q": "طماطم"}).json()["crops"]} == {"tomato"}


def test_hardware_pdf_export(client):
    r = client.get("/api/v1/hardware-guide/export?zone_id=1")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF" and len(r.content) > 20000


def test_zone_reset_clears_entered_data(client):
    client.post("/api/v1/simulator/push", json={"zone_id": 2, "case_id": "R2"})
    client.post("/api/v1/optimize/prescription", json={"zone_id": 2, "crop_slug": "tomato"})
    r = client.post("/api/v1/zones/2/reset", json={})
    assert r.status_code == 200 and r.json()["deleted"]["readings"] > 0
    dash = client.get("/api/v1/zones/2/dashboard").json()
    assert dash["latest"] is None and dash["alerts"] == [] and dash["lab"] == {}
    assert client.get("/api/v1/prescriptions?zone_id=2").json()["prescriptions"] == []
    assert client.get("/api/v1/zones/2").json()["zone"]["name"].startswith("Zone B")   # zone kept
    # fresh data can be added straight away
    assert client.post("/api/v1/simulator/push", json={"zone_id": 2, "case_id": "R3"}).status_code == 200


def test_zone_reset_partial_keeps_lab(client):
    client.post("/api/v1/simulator/push", json={"zone_id": 2, "case_id": "R5"})
    client.post("/api/v1/zones/2/reset", json={"lab": False})
    assert client.get("/api/v1/zones/2").json()["lab"]["texture_class"] == "sandy_loam"
    assert client.get("/api/v1/zones/2/dashboard").json()["latest"] is None


def test_no_actuator_endpoints():
    paths = {getattr(r, "path", "") for r in app.routes}
    for word in ("valve", "relay", "pump", "actuat", "command", "downlink"):
        assert not any(word in p for p in paths)
