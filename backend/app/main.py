"""FastAPI application — Advisory-Only, Sensors-Only Smart Soil platform.

Endpoints follow spec Section 8.3. The platform never sends downlink or
actuator commands; every output is advice for the farmer.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .engine import alerts as alert_engine
from .engine import matcher, prescription
from .engine.pipeline import health_index
from .knowledge import soil as soil_kb
from .knowledge.crops import CROP_BY_SLUG, CROPS, SEASON_MONTHS, SEASON_NAMES, STAGE_NAMES, STAGES, stage_kc
from .knowledge.test_cases import CASE_BY_ID, TEST_CASES
from .schemas import (DeviceIn, LabProfileIn, PrescriptionIn, SimulatorPush, SimulatorRandom,
                      TelemetryPayload, ZoneIn, ZoneRef, ZoneResetIn)
from .services import repository as repo
from .services import simulator
from .services.live import broker

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


app = FastAPI(title="Smart Soil Advisory Platform (Egypt)", version="1.0.0", lifespan=lifespan,
              description="Advisory-only, sensors-only soil analysis and crop optimisation platform.")


def _startup() -> None:
    db.init()
    info = repo.seed()
    if info.get("seed_token"):
        print("\n  Seeded device EGY-NODE-001. API token (also saved to data/seed_device_token.txt):")
        print(f"  {info['seed_token']}\n")
    _maybe_start_mqtt()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _zone_or_404(zone_id: int) -> dict:
    z = repo.zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    return z


def _state_or_409(zone_id: int):
    _zone_or_404(zone_id)
    st = repo.field_state(zone_id)
    if st is None:
        raise HTTPException(409, "No sensor readings for this zone yet — connect hardware or use the simulator.")
    return st


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------
def _crop_public(c: dict) -> dict:
    out = {k: (list(v) if isinstance(v, (tuple, set)) else v) for k, v in c.items()}
    out["stages"] = [{"stage": s, "en": STAGE_NAMES[s]["en"], "ar": STAGE_NAMES[s]["ar"], "kc_ext": stage_kc(c, s),
                      "vpd_target": list(repo.VPD_STAGE[s])} for s in STAGES]
    return out


@app.get("/api/v1/meta")
def meta():
    return {
        "crops": [{"slug": c["slug"], "name_en": c["name_en"], "name_ar": c["name_ar"]} for c in CROPS],
        "stages": [{"id": s, **STAGE_NAMES[s]} for s in STAGES],
        "seasons": [{"id": s, **SEASON_NAMES[s], "months": sorted(SEASON_MONTHS[s])} for s in SEASON_NAMES],
        "textures": [{"id": k, "en": v["en"], "ar": v["ar"], "fc": v["fc"], "pwp": v["pwp"], "external": v["external"]}
                     for k, v in soil_kb.TEXTURES.items()],
        "regions": [{"id": k, "en": v["en"], "ar": v["ar"]} for k, v in soil_kb.REGIONS.items()],
        "simulator_modes": [{"id": k, **v} for k, v in simulator.MODES.items()],
        "test_cases": [{"id": c["id"], "title_en": c["title_en"], "title_ar": c["title_ar"]} for c in TEST_CASES],
    }


@app.get("/api/v1/crops")
def crops(q: str | None = None, season: str | None = None, max_ec: float | None = None, min_ec: float | None = None):
    out = []
    for c in CROPS:
        text = " ".join([c["name_en"], c["name_ar"], c["scientific"], c["slug"]]).lower()
        if q and q.lower() not in text:
            continue
        if season and not (c["perennial"] or c["season_scores"].get(season, 0) >= 0.8):
            continue
        if min_ec is not None and c["ec_limit"] < min_ec:
            continue
        if max_ec is not None and c["ec_limit"] > max_ec:
            continue
        out.append(_crop_public(c))
    return {"crops": out, "remediation_rules": soil_kb.REMEDIATION_RULES}


@app.get("/api/v1/knowledge")
def knowledge():
    return {"probe_parameters": soil_kb.PROBE_PARAMETERS, "lab_traits": soil_kb.LAB_TRAITS,
            "microclimate": soil_kb.MICROCLIMATE_METRICS, "macronutrients": soil_kb.MACRONUTRIENTS,
            "micronutrients": soil_kb.MICRONUTRIENTS, "remediation_rules": soil_kb.REMEDIATION_RULES,
            "textures": soil_kb.TEXTURES, "fertilizers": soil_kb.FERTILIZERS}


# ---------------------------------------------------------------------------
# Zones, lab profiles, dashboard
# ---------------------------------------------------------------------------
@app.get("/api/v1/zones")
def list_zones():
    zones = db.q("SELECT z.*, f.name AS farm_name FROM field_zones z JOIN farms f ON f.id = z.farm_id ORDER BY z.id")
    for z in zones:
        last = db.q1("SELECT time, shi FROM sensor_readings WHERE zone_id = ? ORDER BY id DESC LIMIT 1", (z["id"],))
        z["last_reading_at"] = last["time"] if last else None
        z["shi"] = last["shi"] if last else None
        sev = db.q("SELECT severity FROM advisory_alerts WHERE zone_id = ? AND active = 1", (z["id"],))
        z["status"] = alert_engine.overall_status([{"severity": s["severity"]} for s in sev]) if last else None
    return {"zones": zones}


@app.post("/api/v1/zones")
def create_zone(body: ZoneIn):
    farm = db.q1("SELECT id FROM farms ORDER BY id LIMIT 1")
    data = {k: v for k, v in body.model_dump().items() if v is not None and k in ZoneIn.model_fields}
    data.setdefault("name", "New Zone")
    data["farm_id"] = farm["id"]
    zid = db.insert("field_zones", data)
    return repo.zone(zid)


@app.get("/api/v1/zones/{zone_id}")
def get_zone(zone_id: int):
    z = _zone_or_404(zone_id)
    return {"zone": z, "lab": repo.lab_profile(zone_id), "devices": repo.devices_for_zone(zone_id),
            "context": repo.zone_context(z)}


@app.patch("/api/v1/zones/{zone_id}")
def patch_zone(zone_id: int, body: ZoneIn):
    _zone_or_404(zone_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in ZoneIn.model_fields}
    if "active_crop_id" in data and data["active_crop_id"] not in (None, "") and data["active_crop_id"] not in CROP_BY_SLUG:
        raise HTTPException(422, "Unknown crop")
    if data.get("active_crop_id") == "":
        data["active_crop_id"] = None
    db.update("field_zones", "id", zone_id, data)
    _reevaluate(zone_id)
    return repo.zone(zone_id)


@app.put("/api/v1/zones/{zone_id}/lab-profile")
def put_lab(zone_id: int, body: LabProfileIn):
    _zone_or_404(zone_id)
    if body.texture_class and body.texture_class not in soil_kb.TEXTURES:
        raise HTTPException(422, f"texture_class must be one of {list(soil_kb.TEXTURES)}")
    result = repo.save_lab_profile(zone_id, body.model_dump())
    _reevaluate(zone_id)
    return result


@app.post("/api/v1/zones/{zone_id}/reset")
def reset_zone(zone_id: int, body: ZoneResetIn | None = None):
    """Clear the data entered for a zone so fresh data can be added.
    The zone itself, its crop/stage settings and its registered devices are kept."""
    _zone_or_404(zone_id)
    opts = body or ZoneResetIn()
    deleted = {}
    if opts.readings:
        deleted["readings"] = db.q1("SELECT COUNT(*) AS n FROM sensor_readings WHERE zone_id = ?", (zone_id,))["n"]
        db.ex("DELETE FROM sensor_readings WHERE zone_id = ?", (zone_id,))
        db.ex("UPDATE iot_devices SET status = 'offline', last_seen_at = NULL, battery_v = NULL, rssi_dbm = NULL "
              "WHERE zone_id = ?", (zone_id,))
        db.update("field_zones", "id", zone_id, {"chill_hours_override": None, "context_month": None})
    if opts.alerts:
        deleted["alerts"] = db.q1("SELECT COUNT(*) AS n FROM advisory_alerts WHERE zone_id = ?", (zone_id,))["n"]
        db.ex("DELETE FROM advisory_alerts WHERE zone_id = ?", (zone_id,))
    if opts.prescriptions:
        deleted["prescriptions"] = db.q1("SELECT COUNT(*) AS n FROM soil_prescriptions WHERE zone_id = ?", (zone_id,))["n"]
        db.ex("DELETE FROM soil_prescriptions WHERE zone_id = ?", (zone_id,))
    if opts.lab:
        deleted["lab_profiles"] = db.q1("SELECT COUNT(*) AS n FROM lab_soil_profiles WHERE zone_id = ?", (zone_id,))["n"]
        db.ex("DELETE FROM lab_soil_profiles WHERE zone_id = ?", (zone_id,))
        db.ex("UPDATE iot_devices SET npk_calibration_json = '{}' WHERE zone_id = ?", (zone_id,))
    broker.publish("zone", {"zone_id": zone_id, "reset": True}, zone_id)
    return {"zone_id": zone_id, "deleted": deleted}


def _reevaluate(zone_id: int) -> None:
    """Re-run alerts after context/lab changes so the dashboard stays consistent."""
    st = repo.field_state(zone_id)
    if st is None:
        return
    repo.sync_alerts(zone_id, alert_engine.evaluate(st, st.context.get("crop_slug")))
    broker.publish("zone", {"zone_id": zone_id}, zone_id)


@app.get("/api/v1/zones/{zone_id}/dashboard")
def dashboard(zone_id: int, history: int = Query(48, ge=1, le=500)):
    z = _zone_or_404(zone_id)
    rows = repo.readings(zone_id, history)
    lab = repo.lab_profile(zone_id)
    ctx = repo.zone_context(z)
    out = {"zone": z, "lab": lab, "context": ctx, "devices": repo.devices_for_zone(zone_id),
           "latest": None, "history": list(reversed(rows)), "alerts": [], "status": None, "shi": None}
    if not rows:
        return out
    st = repo.field_state(zone_id)
    crop = CROP_BY_SLUG.get(ctx.get("crop_slug")) if ctx.get("crop_slug") else None
    latest = dict(rows[0])
    latest["dew_point_spread"] = None if st.dew_point_spread is None else round(st.dew_point_spread, 1)
    latest["esp_effective"] = st.esp
    out["latest"] = latest
    out["shi"] = health_index(st, crop)
    alerts = db.q("SELECT * FROM advisory_alerts WHERE zone_id = ? AND active = 1 ORDER BY "
                  "CASE severity WHEN 'red' THEN 0 WHEN 'amber' THEN 1 ELSE 2 END, id DESC", (zone_id,))
    out["alerts"] = alerts
    out["status"] = alert_engine.overall_status(alerts)
    out["crop"] = _crop_public(crop) if crop else None
    out["seasons_active"] = sorted(st.seasons)
    return out


@app.get("/api/v1/zones/{zone_id}/readings")
def zone_readings(zone_id: int, limit: int = Query(100, ge=1, le=2000)):
    _zone_or_404(zone_id)
    return {"readings": repo.readings(zone_id, limit)}


# ---------------------------------------------------------------------------
# Telemetry ingestion (hardware) — one-way uplink
# ---------------------------------------------------------------------------
@app.post("/api/v1/telemetry/ingest")
def telemetry_ingest(payload: TelemetryPayload, authorization: str | None = Header(None),
                     x_device_token: str | None = Header(None)):
    token = x_device_token or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
    dev = repo.authenticate_device(payload.device_id, token)
    if not dev:
        raise HTTPException(401, "Unknown device or invalid API token")
    data = payload.model_dump()
    if not data.get("timestamp_utc"):
        data["timestamp_utc"] = _now()
    summary = repo.ingest(data, dev["zone_id"], source="hardware")
    return {"accepted": True, "advisory_only": True, **summary}


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------
def _apply_bundle_context(zone_id: int, lab: dict | None, context: dict | None) -> None:
    if lab:
        repo.save_lab_profile(zone_id, lab)
    if context:
        upd = {}
        if context.get("region"):
            upd["governorate"] = context["region"]
        if context.get("season"):
            upd["season"] = context["season"]
        if context.get("irrigation_type"):
            upd["irrigation_type"] = context["irrigation_type"]
        upd["chill_hours_override"] = context.get("chill_hours")
        upd["context_month"] = context.get("month")
        db.update("field_zones", "id", zone_id, upd)


def _sim_ingest(zone_id: int, sensors: dict, fillers: dict) -> dict:
    z = _zone_or_404(zone_id)
    crop = CROP_BY_SLUG.get(z.get("active_crop_id") or "")
    devs = repo.devices_for_zone(zone_id)
    payload = simulator.build_payload(
        sensors, fillers, device_id=(devs[0]["device_id"] if devs else f"SIM-ZONE-{zone_id}"),
        farm_id=str(z["farm_id"]), zone_id=str(zone_id),
        upper_depth=crop["upper_depth_cm"] if crop else 15, lower_depth=crop["lower_depth_cm"] if crop else 35)
    payload["device_id"] = f"SIM-ZONE-{zone_id}"  # never touches real device health records
    return repo.ingest(payload, zone_id, source="simulator")


@app.get("/api/v1/simulator/cases")
def sim_cases():
    out = []
    for c in TEST_CASES:
        payload = simulator.build_payload(c["sensors"], c["fillers"], device_id="SIM", farm_id="SIM", zone_id="SIM")
        out.append({**c, "payload_preview": payload})
    return {"cases": out, "modes": simulator.MODES}


@app.post("/api/v1/simulator/push")
def sim_push(body: SimulatorPush):
    _zone_or_404(body.zone_id)
    if body.case_id:
        if body.case_id not in CASE_BY_ID:
            raise HTTPException(404, "Unknown case id")
        b = simulator.case_bundle(body.case_id)
        _apply_bundle_context(body.zone_id, b["lab"], b["context"])
        summary = _sim_ingest(body.zone_id, b["sensors"], b["fillers"])
        return {"case": body.case_id, **summary}
    if not body.sensors:
        raise HTTPException(422, "Provide case_id or sensors")
    s = body.sensors.model_dump()
    fillers = {"o2_pct": s.pop("o2_pct", None), "par": s.pop("par", None),
               "leaf_wetness_pct": s.pop("leaf_wetness_pct", None), "wind_ms": s.pop("wind_ms", None)}
    _apply_bundle_context(body.zone_id, body.lab.model_dump(exclude_none=True) if body.lab else None, body.context)
    return _sim_ingest(body.zone_id, s, fillers)


@app.post("/api/v1/simulator/random")
def sim_random(body: SimulatorRandom):
    _zone_or_404(body.zone_id)
    b = simulator.random_bundle(body.mode, body.seed)
    _apply_bundle_context(body.zone_id, b["lab"], b["context"])
    summary = _sim_ingest(body.zone_id, b["sensors"], b["fillers"])
    return {"mode": b["mode"], "mode_effective": b["mode_effective"], "generated": b, **summary}


# ---------------------------------------------------------------------------
# Optimisation engine
# ---------------------------------------------------------------------------
@app.post("/api/v1/optimize/match-crops")
def match_crops(body: ZoneRef):
    st = _state_or_409(body.zone_id)
    ranked = matcher.match_all(st)
    return {"zone_id": body.zone_id, "seasons_active": sorted(st.seasons), "greenhouse": st.greenhouse,
            "weights": matcher.WEIGHTS, "dimension_names": matcher.DIM_NAMES, "ranking": ranked}


@app.post("/api/v1/optimize/prescription")
def make_prescription(body: PrescriptionIn):
    st = _state_or_409(body.zone_id)
    z = repo.zone(body.zone_id)
    crop_slug = body.crop_slug or z.get("active_crop_id") or matcher.match_all(st)[0]["slug"]
    if crop_slug not in CROP_BY_SLUG:
        raise HTTPException(422, "Unknown crop")
    stage = body.stage or z.get("growth_stage") or "vegetative"
    rx = prescription.build(st, crop_slug, stage)
    rx["zone"] = {"id": z["id"], "name": z["name"], "area_feddan": z["area_feddan"]}
    rx["generated_at"] = _now()
    rx["reading_time"] = st.reading.get("time")
    pid = db.insert("soil_prescriptions", {
        "zone_id": body.zone_id, "crop_id": crop_slug, "growth_stage": stage,
        "soil_health_index": rx["soil_health_index"]["index"],
        "conditioning_additions_json": db.dumps(rx["conditioning"]),
        "irrigation_leaching_json": db.dumps(rx["irrigation"]),
        "tank_a_b_acid_plan_json": db.dumps(rx["macronutrients"]),
        "micronutrients_biostimulants_json": db.dumps(rx["biostimulants"]),
        "warnings_en_ar_json": db.dumps(rx["alerts"]),
        "full_json": db.dumps(rx), "created_at": rx["generated_at"]})
    rx["id"] = pid
    return rx


@app.get("/api/v1/prescriptions")
def list_prescriptions(zone_id: int | None = None, limit: int = 20):
    if zone_id:
        rows = db.q("SELECT id, zone_id, crop_id, growth_stage, soil_health_index, created_at FROM soil_prescriptions "
                    "WHERE zone_id = ? ORDER BY id DESC LIMIT ?", (zone_id, limit))
    else:
        rows = db.q("SELECT id, zone_id, crop_id, growth_stage, soil_health_index, created_at FROM soil_prescriptions "
                    "ORDER BY id DESC LIMIT ?", (limit,))
    return {"prescriptions": rows}


@app.get("/api/v1/prescriptions/{pid}")
def get_prescription(pid: int):
    row = db.q1("SELECT full_json FROM soil_prescriptions WHERE id = ?", (pid,))
    if not row:
        raise HTTPException(404, "Prescription not found")
    rx = db.loads(row["full_json"], {})
    rx["id"] = pid
    return rx


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
@app.get("/api/v1/alerts")
def list_alerts(zone_id: int | None = None, active: bool | None = None, limit: int = 100):
    sql, params = "SELECT * FROM advisory_alerts WHERE 1=1", []
    if zone_id:
        sql += " AND zone_id = ?"; params.append(zone_id)
    if active is not None:
        sql += " AND active = ?"; params.append(1 if active else 0)
    sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)
    return {"alerts": db.q(sql, params)}


@app.post("/api/v1/alerts/{alert_id}/ack")
def ack_alert(alert_id: int):
    if not db.q1("SELECT id FROM advisory_alerts WHERE id = ?", (alert_id,)):
        raise HTTPException(404, "Alert not found")
    db.update("advisory_alerts", "id", alert_id, {"acknowledged": 1, "updated_at": _now()})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
@app.get("/api/v1/devices")
def list_devices():
    rows = db.q("SELECT device_id, zone_id, upper_depth_cm, lower_depth_cm, status, last_seen_at, battery_v, rssi_dbm, "
                "firmware_version, npk_calibration_json FROM iot_devices ORDER BY device_id")
    for r in rows:
        r["status"] = repo.device_status(r)
        r["npk_calibration"] = db.loads(r.pop("npk_calibration_json"), {})
    return {"devices": rows}


@app.post("/api/v1/devices")
def create_device(body: DeviceIn):
    _zone_or_404(body.zone_id)
    if db.q1("SELECT device_id FROM iot_devices WHERE device_id = ?", (body.device_id,)):
        raise HTTPException(409, "Device already exists — rotate its token instead")
    token = repo.new_token()
    db.insert("iot_devices", {"device_id": body.device_id, "zone_id": body.zone_id, "api_key_hash": repo.hash_token(token),
                              "upper_depth_cm": body.upper_depth_cm, "lower_depth_cm": body.lower_depth_cm,
                              "status": "offline", "npk_calibration_json": "{}"})
    return {"device_id": body.device_id, "token": token, "note": "Store this token now — only its hash is kept."}


@app.post("/api/v1/devices/{device_id}/rotate-token")
def rotate_token(device_id: str):
    if not db.q1("SELECT device_id FROM iot_devices WHERE device_id = ?", (device_id,)):
        raise HTTPException(404, "Device not found")
    token = repo.new_token()
    db.update("iot_devices", "device_id", device_id, {"api_key_hash": repo.hash_token(token)})
    return {"device_id": device_id, "token": token, "note": "Store this token now — only its hash is kept."}


# ---------------------------------------------------------------------------
# Hardware BOM & firmware PDF
# ---------------------------------------------------------------------------
@app.get("/api/v1/hardware-guide/export")
def hardware_export(request: Request, zone_id: int | None = None, device_id: str | None = None):
    from .services.hardware_pdf import build_pdf
    dev = None
    if device_id:
        dev = db.q1("SELECT * FROM iot_devices WHERE device_id = ?", (device_id,))
    elif zone_id:
        dev = db.q1("SELECT * FROM iot_devices WHERE zone_id = ? LIMIT 1", (zone_id,))
    z = repo.zone(dev["zone_id"]) if dev else (repo.zone(zone_id) if zone_id else None)
    crop = CROP_BY_SLUG.get(z.get("active_crop_id")) if z and z.get("active_crop_id") else None
    base = str(request.base_url).rstrip("/")
    pdf = build_pdf(device_id=dev["device_id"] if dev else "EGY-NODE-001",
                    ingest_url=f"{base}/api/v1/telemetry/ingest",
                    zone_name=z["name"] if z else None, crop=crop)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="Hardware_BOM_Wiring_Firmware.pdf"'})


# ---------------------------------------------------------------------------
# Live stream (SSE)
# ---------------------------------------------------------------------------
@app.get("/api/v1/stream")
async def stream(request: Request, zone_id: int | None = None):
    q = broker.subscribe(zone_id)

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            broker.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v1/health")
def health():
    return {"ok": True, "time": _now(), "mode": "advisory-only, sensors-only"}


# ---------------------------------------------------------------------------
# Optional MQTT subscriber (set SOIL_MQTT_HOST). Topic: farms/{farm}/zones/{zone}/telemetry
# Payload must include "api_token" alongside the Section 6.2 fields.
# ---------------------------------------------------------------------------
def _maybe_start_mqtt() -> None:
    host = os.environ.get("SOIL_MQTT_HOST")
    if not host:
        return
    try:
        import json as _json

        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        print("  SOIL_MQTT_HOST set but paho-mqtt is not installed — MQTT ingestion disabled.")
        return

    def on_message(_c, _u, msg):
        try:
            data = _json.loads(msg.payload.decode("utf-8"))
            token = data.pop("api_token", None)
            payload = TelemetryPayload(**data).model_dump()
            dev = repo.authenticate_device(payload["device_id"], token)
            if dev:
                repo.ingest(payload, dev["zone_id"], source="hardware")
        except Exception as exc:  # noqa: BLE001 — never crash the subscriber thread
            print("MQTT message rejected:", exc)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.environ.get("SOIL_MQTT_USER"):
        client.username_pw_set(os.environ["SOIL_MQTT_USER"], os.environ.get("SOIL_MQTT_PASS"))
    if os.environ.get("SOIL_MQTT_TLS", "1") == "1":
        client.tls_set()
    client.on_message = on_message
    client.connect(host, int(os.environ.get("SOIL_MQTT_PORT", "8883")))
    client.subscribe("farms/+/zones/+/telemetry", qos=1)
    client.loop_start()
    print(f"  MQTT subscriber connected to {host}")


# ---------------------------------------------------------------------------
# Frontend (static single-page app)
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    f = FRONTEND_DIR / "index.html"
    if f.exists():
        return FileResponse(f)
    return JSONResponse({"message": "Frontend not found", "docs": "/docs"})
