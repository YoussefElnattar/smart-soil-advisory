"""SQLite storage (spec Section 8.2 schema). Stdlib sqlite3 — zero setup.

The schema mirrors the spec tables; a PostgreSQL/TimescaleDB deployment can
reuse the same column names (sensor_readings becomes a hypertable on `time`).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "smart_soil.db"
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_db_path: Path | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    governorate TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS field_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    name TEXT NOT NULL,
    governorate TEXT,                 -- region id (knowledge.soil.REGIONS)
    area_feddan REAL DEFAULT 1.0,
    irrigation_type TEXT DEFAULT 'drip',   -- drip / greenhouse / pivot
    season TEXT DEFAULT 'auto',            -- auto / shetwi / seifi / nili
    active_crop_id TEXT,                   -- crop slug
    growth_stage TEXT DEFAULT 'vegetative',
    planting_date TEXT,
    expected_harvest_date TEXT,
    chill_hours_override REAL,
    context_month INTEGER,                 -- simulator-pinned month (NULL = from reading time)
    is_sandbox INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS iot_devices (
    device_id TEXT PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES field_zones(id),
    api_key_hash TEXT NOT NULL,
    upper_depth_cm INTEGER DEFAULT 15,
    lower_depth_cm INTEGER DEFAULT 35,
    status TEXT DEFAULT 'offline',          -- online / offline / fault
    npk_calibration_json TEXT DEFAULT '{}',
    last_seen_at TEXT,
    battery_v REAL,
    rssi_dbm REAL,
    firmware_version TEXT
);
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    device_id TEXT,
    zone_id INTEGER NOT NULL,
    source TEXT DEFAULT 'hardware',         -- hardware / simulator
    upper_depth_cm REAL, lower_depth_cm REAL,
    vwc_upper REAL, vwc_lower REAL, awc_upper REAL, awc_lower REAL,
    matric_kpa REAL,
    soil_temp_upper REAL, soil_temp_lower REAL,
    ec_bulk_upper REAL, ec_pore_upper REAL, ec_pore_lower REAL, ec25_upper REAL, ec25_lower REAL,
    ph REAL,
    n_ppm REAL, p_ppm REAL, k_ppm REAL, n_cal REAL, p_cal REAL, k_cal REAL, npk_calibrated INTEGER,
    orp_mv REAL, o2_pct REAL,
    air_temp_c REAL, rh_pct REAL, vpd_kpa REAL, par REAL, leaf_wetness REAL, wind_ms REAL, rain_mm REAL,
    battery_v REAL, solar_ma REAL, rssi_dbm REAL, firmware_version TEXT,
    fault_flags_json TEXT DEFAULT '[]',
    shi REAL
);
CREATE INDEX IF NOT EXISTS ix_readings_zone_time ON sensor_readings(zone_id, time);
CREATE TABLE IF NOT EXISTS lab_soil_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL REFERENCES field_zones(id),
    sample_date TEXT,
    texture_class TEXT, sand_pct REAL, silt_pct REAL, clay_pct REAL,
    cec_meq REAL, som_pct REAL, caco3_pct REAL, esp_pct REAL, sar REAL, bulk_density REAL,
    water_table_m REAL,
    water_ec_w REAL, water_ph REAL, water_hco3 REAL, water_boron_ppm REAL, water_cl_ppm REAL,
    lab_n_ppm REAL, lab_p_ppm REAL, lab_k_ppm REAL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS crop_profiles (
    slug TEXT PRIMARY KEY,
    name_en TEXT, name_ar TEXT, scientific_name TEXT,
    preferred_textures TEXT, ph_min REAL, ph_max REAL, ec_limit_ds_m REAL,
    upper_depth_cm INTEGER, lower_depth_cm INTEGER, awc_min REAL, awc_max REAL,
    tension_min_kpa REAL, tension_max_kpa REAL,
    seasons_json TEXT, day_night_temp_json TEXT, rh_min REAL, rh_max REAL,
    chill_hours_req TEXT, nutrition_strategy_json TEXT, sensor_rules_json TEXT,
    full_json TEXT
);
CREATE TABLE IF NOT EXISTS crop_growth_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id TEXT NOT NULL REFERENCES crop_profiles(slug),
    stage_name TEXT NOT NULL,
    kc_factor REAL,
    n_p_k_ca_mg_ratios TEXT,
    vpd_target_min REAL, vpd_target_max REAL,
    stage_notes TEXT
);
CREATE TABLE IF NOT EXISTS soil_prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    crop_id TEXT, growth_stage TEXT,
    soil_health_index REAL,
    conditioning_additions_json TEXT, irrigation_leaching_json TEXT, tank_a_b_acid_plan_json TEXT,
    micronutrients_biostimulants_json TEXT, warnings_en_ar_json TEXT,
    full_json TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS advisory_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    severity TEXT NOT NULL,            -- green / amber / red
    rule_code TEXT NOT NULL,
    message_en TEXT, message_ar TEXT,
    recommended_farmer_action TEXT, recommended_farmer_action_ar TEXT,
    source TEXT,
    acknowledged INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT
);
"""

READING_COLUMNS = [
    "time", "device_id", "zone_id", "source", "upper_depth_cm", "lower_depth_cm",
    "vwc_upper", "vwc_lower", "awc_upper", "awc_lower", "matric_kpa", "soil_temp_upper", "soil_temp_lower",
    "ec_bulk_upper", "ec_pore_upper", "ec_pore_lower", "ec25_upper", "ec25_lower", "ph",
    "n_ppm", "p_ppm", "k_ppm", "n_cal", "p_cal", "k_cal", "npk_calibrated", "orp_mv", "o2_pct",
    "air_temp_c", "rh_pct", "vpd_kpa", "par", "leaf_wetness", "wind_ms", "rain_mm",
    "battery_v", "solar_ma", "rssi_dbm", "firmware_version", "shi",
]

LAB_COLUMNS = [
    "sample_date", "texture_class", "sand_pct", "silt_pct", "clay_pct", "cec_meq", "som_pct", "caco3_pct",
    "esp_pct", "sar", "bulk_density", "water_table_m", "water_ec_w", "water_ph", "water_hco3",
    "water_boron_ppm", "water_cl_ppm", "lab_n_ppm", "lab_p_ppm", "lab_k_ppm",
]


def init(path: str | Path | None = None) -> sqlite3.Connection:
    global _conn, _db_path
    with _lock:
        p = Path(path or os.environ.get("SOIL_DB_PATH") or DEFAULT_DB)
        if _conn is not None and _db_path == p:
            return _conn
        if str(p) != ":memory:":
            p.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(p), check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL" if str(p) != ":memory:" else "PRAGMA journal_mode=MEMORY")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.executescript(SCHEMA)
        _db_path = p
        return _conn


def conn() -> sqlite3.Connection:
    return _conn or init()


def q(sql: str, params: tuple | list = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def q1(sql: str, params: tuple | list = ()) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql: str, params: tuple | list = ()) -> int:
    with _lock:
        cur = conn().execute(sql, params)
        return cur.lastrowid


def insert(table: str, data: dict) -> int:
    cols = list(data)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    return ex(sql, [data[c] for c in cols])


def update(table: str, key: str, key_value, data: dict) -> None:
    if not data:
        return
    sets = ", ".join(f"{c} = ?" for c in data)
    ex(f"UPDATE {table} SET {sets} WHERE {key} = ?", [*data.values(), key_value])


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text, default=None):
    if text in (None, ""):
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default
