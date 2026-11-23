"""Data access + the ingestion service shared by hardware and simulator."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from ..engine import alerts as alert_engine
from ..engine.pipeline import health_index, process_payload
from ..engine.state import FieldState
from ..knowledge.crops import CROP_BY_SLUG, CROPS, STAGES, stage_kc
from ..knowledge.soil import STAGE_NPK_TARGET_PPM_EXT
from .live import broker

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return "sk_dev_" + secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
VPD_STAGE = {"establishment": (0.8, 1.2), "vegetative": (0.8, 1.2), "flowering": (1.0, 1.5), "ripening": (1.0, 1.5)}


def seed() -> dict:
    """Idempotent. Seeds the 10 crops, their 4 stages, a demo farm with a live
    hardware zone + a simulator sandbox zone, and one device token."""
    info: dict = {}
    if not db.q1("SELECT slug FROM crop_profiles LIMIT 1"):
        for c in CROPS:
            db.insert("crop_profiles", {
                "slug": c["slug"], "name_en": c["name_en"], "name_ar": c["name_ar"], "scientific_name": c["scientific"],
                "preferred_textures": db.dumps(c["preferred_textures"]), "ph_min": c["ph_min"], "ph_max": c["ph_max"],
                "ec_limit_ds_m": c["ec_limit"], "upper_depth_cm": c["upper_depth_cm"], "lower_depth_cm": c["lower_depth_cm"],
                "awc_min": c["awc_min"], "awc_max": c["awc_max"], "tension_min_kpa": c["tension_min"],
                "tension_max_kpa": c["tension_max"], "seasons_json": db.dumps({"text_en": c["seasons_en"], "scores": c["season_scores"]}),
                "day_night_temp_json": db.dumps({"day": c["day_temp"], "night": c["night_temp"]}),
                "rh_min": c["rh"][0], "rh_max": c["rh"][1], "chill_hours_req": db.dumps(c["chill_hours"]),
                "nutrition_strategy_json": db.dumps({"npk": c["npk_focus_en"], "micro": c["micro_focus_en"]}),
                "sensor_rules_json": db.dumps({"rule": c["sensor_rule_en"]}),
                "full_json": db.dumps({k: (list(v) if isinstance(v, (tuple, set)) else v) for k, v in c.items()}),
            })
            for s in STAGES:
                db.insert("crop_growth_stages", {
                    "crop_id": c["slug"], "stage_name": s, "kc_factor": stage_kc(c, s),
                    "n_p_k_ca_mg_ratios": db.dumps(STAGE_NPK_TARGET_PPM_EXT[s]),
                    "vpd_target_min": VPD_STAGE[s][0], "vpd_target_max": VPD_STAGE[s][1],
                    "stage_notes": "Kc from FAO-56 (external); VPD targets from spec Section 1.3",
                })
    if not db.q1("SELECT id FROM farms LIMIT 1"):
        farm_id = db.insert("farms", {"name": "Demo Farm", "governorate": "ismailia"})
        z1 = db.insert("field_zones", {"farm_id": farm_id, "name": "Zone A — Field Hardware", "governorate": "ismailia",
                                       "area_feddan": 5, "irrigation_type": "drip", "season": "auto",
                                       "active_crop_id": "tomato", "growth_stage": "vegetative", "is_sandbox": 0})
        db.insert("field_zones", {"farm_id": farm_id, "name": "Zone B — Simulator Sandbox", "governorate": "nubaria",
                                  "area_feddan": 1, "irrigation_type": "drip", "season": "auto",
                                  "active_crop_id": None, "growth_stage": "establishment", "is_sandbox": 1})
        db.insert("lab_soil_profiles", {"zone_id": z1, "sample_date": datetime.now(timezone.utc).date().isoformat(),
                                        "texture_class": "sandy_loam", "cec_meq": 12, "som_pct": 1.2, "caco3_pct": 6,
                                        "esp_pct": 5, "sar": 4, "bulk_density": 1.5, "water_ec_w": 0.8, "water_ph": 7.4,
                                        "water_hco3": 2.5, "water_boron_ppm": 0.3, "water_cl_ppm": 110})
        token = os.environ.get("SOIL_SEED_TOKEN") or new_token()
        db.insert("iot_devices", {"device_id": "EGY-NODE-001", "zone_id": z1, "api_key_hash": hash_token(token),
                                  "upper_depth_cm": 15, "lower_depth_cm": 35, "status": "offline",
                                  "npk_calibration_json": "{}"})
        try:
            if str(db._db_path) == ":memory:":
                raise OSError("in-memory database — do not persist the token")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            (DATA_DIR / "seed_device_token.txt").write_text(
                f"device_id=EGY-NODE-001\ntoken={token}\n", encoding="utf-8")
        except OSError:
            pass
        info["seed_token"] = token
    return info


# ---------------------------------------------------------------------------
# Zones / lab / devices
# ---------------------------------------------------------------------------
def zone(zone_id: int) -> dict | None:
    return db.q1("SELECT * FROM field_zones WHERE id = ?", (zone_id,))


def lab_profile(zone_id: int) -> dict:
    row = db.q1("SELECT * FROM lab_soil_profiles WHERE zone_id = ? ORDER BY id DESC LIMIT 1", (zone_id,))
    return row or {}


def devices_for_zone(zone_id: int) -> list[dict]:
    rows = db.q("SELECT device_id, zone_id, upper_depth_cm, lower_depth_cm, status, npk_calibration_json, last_seen_at, "
                "battery_v, rssi_dbm, firmware_version FROM iot_devices WHERE zone_id = ?", (zone_id,))
    for r in rows:
        r["npk_calibration"] = db.loads(r.pop("npk_calibration_json"), {})
        r["status"] = device_status(r)
    return rows


OFFLINE_AFTER_S = 45 * 60  # 3 missed 15-min uplinks


def device_status(dev: dict) -> str:
    if not dev.get("last_seen_at"):
        return "offline"
    try:
        seen = datetime.fromisoformat(dev["last_seen_at"].replace("Z", "+00:00"))
    except ValueError:
        return "offline"
    if (datetime.now(timezone.utc) - seen).total_seconds() > OFFLINE_AFTER_S:
        return "offline"
    return dev.get("status") or "online"


def zone_calibration(zone_id: int) -> dict:
    row = db.q1("SELECT npk_calibration_json FROM iot_devices WHERE zone_id = ? ORDER BY last_seen_at DESC LIMIT 1", (zone_id,))
    return db.loads(row["npk_calibration_json"], {}) if row else {}


def save_lab_profile(zone_id: int, data: dict) -> dict:
    data = {k: data.get(k) for k in db.LAB_COLUMNS if k in data}
    data["zone_id"] = zone_id
    if not data.get("sample_date"):
        data["sample_date"] = datetime.now(timezone.utc).date().isoformat()
    db.insert("lab_soil_profiles", data)
    calib = update_npk_calibration(zone_id, data)
    return {"lab": lab_profile(zone_id), "npk_calibration": calib}


def update_npk_calibration(zone_id: int, lab: dict) -> dict:
    """corrected = raw × gain + offset (spec 6.4). One lab point → offset only;
    two or more points → least-squares line through all stored points."""
    latest = db.q1("SELECT n_ppm, p_ppm, k_ppm FROM sensor_readings WHERE zone_id = ? AND source = 'hardware' "
                   "ORDER BY id DESC LIMIT 1", (zone_id,)) or \
        db.q1("SELECT n_ppm, p_ppm, k_ppm FROM sensor_readings WHERE zone_id = ? ORDER BY id DESC LIMIT 1", (zone_id,))
    devs = db.q("SELECT device_id, npk_calibration_json FROM iot_devices WHERE zone_id = ?", (zone_id,))
    if not latest or not devs:
        return {}
    result = {}
    for dev in devs:
        cal = db.loads(dev["npk_calibration_json"], {})
        for n in ("n", "p", "k"):
            lab_v, raw_v = lab.get(f"lab_{n}_ppm"), latest.get(f"{n}_ppm")
            if lab_v is None or raw_v is None:
                continue
            pts = (cal.get(n, {}).get("points") or []) + [[float(raw_v), float(lab_v)]]
            pts = pts[-6:]
            if len(pts) >= 2 and len({p[0] for p in pts}) >= 2:
                mx = sum(p[0] for p in pts) / len(pts)
                my = sum(p[1] for p in pts) / len(pts)
                sxx = sum((p[0] - mx) ** 2 for p in pts)
                gain = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
                offset = my - gain * mx
            else:
                gain, offset = 1.0, float(lab_v) - float(raw_v)
            cal[n] = {"gain": round(gain, 4), "offset": round(offset, 3), "points": pts}
        db.update("iot_devices", "device_id", dev["device_id"], {"npk_calibration_json": db.dumps(cal)})
        result = cal
    return result


def chill_hours(zone_id: int) -> float | None:
    """Hours below 7.2 °C since 1 Nov (winter chill), from stored readings."""
    now = datetime.now(timezone.utc)
    start_year = now.year if now.month >= 11 else now.year - 1
    start = f"{start_year}-11-01T00:00:00Z"
    rows = db.q("SELECT time, air_temp_c FROM sensor_readings WHERE zone_id = ? AND source = 'hardware' AND time >= ? "
                "ORDER BY time", (zone_id, start))
    if len(rows) < 2:
        return None
    hours = 0.0
    for a, b in zip(rows, rows[1:]):
        try:
            ta = datetime.fromisoformat(a["time"].replace("Z", "+00:00"))
            tb = datetime.fromisoformat(b["time"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if a["air_temp_c"] is not None and a["air_temp_c"] < 7.2:
            hours += min((tb - ta).total_seconds() / 3600.0, 1.0)
    return round(hours, 1)


def zone_context(z: dict) -> dict:
    ch = z.get("chill_hours_override")
    if ch is None:
        ch = chill_hours(z["id"])
    return {"region": z.get("governorate"), "season": z.get("season") or "auto",
            "irrigation_type": z.get("irrigation_type") or "drip", "month": z.get("context_month"),
            "chill_hours": ch, "crop_slug": z.get("active_crop_id"), "stage": z.get("growth_stage")}


def readings(zone_id: int, limit: int = 50) -> list[dict]:
    rows = db.q("SELECT * FROM sensor_readings WHERE zone_id = ? ORDER BY id DESC LIMIT ?", (zone_id, limit))
    for r in rows:
        r["fault_flags"] = db.loads(r.pop("fault_flags_json"), [])
    return rows


def field_state(zone_id: int) -> FieldState | None:
    z = zone(zone_id)
    if not z:
        return None
    rows = readings(zone_id, 4)
    if not rows:
        return None
    return FieldState(reading=rows[0], lab=lab_profile(zone_id), context=zone_context(z), history=rows[1:])


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
def sync_alerts(zone_id: int, current: list[dict]) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    active = {r["rule_code"]: r for r in db.q("SELECT * FROM advisory_alerts WHERE zone_id = ? AND active = 1", (zone_id,))}
    codes_now = set()
    for a in current:
        codes_now.add(a["rule_code"])
        if a["rule_code"] in active:
            db.update("advisory_alerts", "id", active[a["rule_code"]]["id"],
                      {"severity": a["severity"], "message_en": a["message_en"], "message_ar": a["message_ar"],
                       "updated_at": now})
        else:
            db.insert("advisory_alerts", {
                "zone_id": zone_id, "severity": a["severity"], "rule_code": a["rule_code"],
                "message_en": a["message_en"], "message_ar": a["message_ar"],
                "recommended_farmer_action": a["action_en"], "recommended_farmer_action_ar": a["action_ar"],
                "source": a["source"], "acknowledged": 0, "active": 1, "created_at": now, "updated_at": now})
    for code, row in active.items():
        if code not in codes_now:
            db.update("advisory_alerts", "id", row["id"], {"active": 0, "updated_at": now})


# ---------------------------------------------------------------------------
# Ingestion (hardware + simulator share this path)
# ---------------------------------------------------------------------------
def ingest(payload: dict, zone_id: int, *, source: str) -> dict:
    lab = lab_profile(zone_id)
    history = readings(zone_id, 3)
    reading = process_payload(payload, lab, history, zone_calibration(zone_id))
    z = zone(zone_id)
    ctx = zone_context(z)
    st = FieldState(reading=reading, lab=lab, context=ctx, history=history)
    crop = CROP_BY_SLUG.get(ctx["crop_slug"]) if ctx.get("crop_slug") else None
    shi = health_index(st, crop)
    reading["shi"] = shi["index"]
    row = {c: reading.get(c) for c in db.READING_COLUMNS}
    row.update({"zone_id": zone_id, "source": source,
                "time": reading.get("time") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "npk_calibrated": 1 if reading.get("npk_calibrated") else 0,
                "fault_flags_json": db.dumps(reading.get("fault_flags") or [])})
    reading_id = db.insert("sensor_readings", row)
    if payload.get("device_id"):
        dev = db.q1("SELECT device_id FROM iot_devices WHERE device_id = ?", (payload["device_id"],))
        if dev:
            hh = payload.get("hardware_health") or {}
            db.update("iot_devices", "device_id", payload["device_id"], {
                "last_seen_at": row["time"], "battery_v": hh.get("battery_v"), "rssi_dbm": hh.get("signal_rssi_dbm"),
                "firmware_version": hh.get("firmware_version"),
                "status": "fault" if reading.get("fault_flags") else "online"})
    alerts = alert_engine.evaluate(st, ctx.get("crop_slug"))
    sync_alerts(zone_id, alerts)
    summary = {"reading_id": reading_id, "zone_id": zone_id, "source": source, "time": row["time"],
               "status": alert_engine.overall_status(alerts), "shi": shi, "alerts": len(alerts),
               "fault_flags": reading.get("fault_flags") or []}
    broker.publish("reading", summary, zone_id)
    return summary


def authenticate_device(device_id: str | None, token: str | None) -> dict | None:
    if not device_id or not token:
        return None
    dev = db.q1("SELECT * FROM iot_devices WHERE device_id = ?", (device_id,))
    if dev and secrets.compare_digest(dev["api_key_hash"], hash_token(token)):
        return dev
    return None
