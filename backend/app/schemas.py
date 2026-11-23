"""Pydantic models — the Section 6.2 uplink contract and API request bodies."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class HardwareHealth(_Open):
    battery_v: Optional[float] = None
    solar_charge_ma: Optional[float] = None
    signal_rssi_dbm: Optional[float] = None
    firmware_version: Optional[str] = None
    fault_flags: list[str] = Field(default_factory=list)
    ec_atc_applied: bool = False  # extension: true when the node already sends EC at 25 °C


class SoilUpper(_Open):
    depth_cm: Optional[float] = None
    vwc_pct: Optional[float] = None
    matric_potential_kpa: Optional[float] = None
    temp_c: Optional[float] = None
    ec_bulk_ds_m: Optional[float] = None
    ec_pore_ds_m: Optional[float] = None
    ph: Optional[float] = None
    n_ppm: Optional[float] = None
    p_ppm: Optional[float] = None
    k_ppm: Optional[float] = None
    orp_mv: Optional[float] = None
    o2_pct: Optional[float] = None


class SoilLower(_Open):
    depth_cm: Optional[float] = None
    vwc_pct: Optional[float] = None
    temp_c: Optional[float] = None
    ec_pore_ds_m: Optional[float] = None


class Microclimate(_Open):
    air_temp_c: Optional[float] = None
    rh_pct: Optional[float] = None
    par_umol_m2_s: Optional[float] = None
    leaf_wetness_pct: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    rain_mm_hr: Optional[float] = None


class TelemetryPayload(_Open):
    schema_version: str = "1.0"
    device_id: str
    farm_id: Optional[str] = None
    zone_id: Optional[str] = None
    timestamp_utc: Optional[str] = None
    hardware_health: HardwareHealth = Field(default_factory=HardwareHealth)
    soil_upper: SoilUpper = Field(default_factory=SoilUpper)
    soil_lower: SoilLower = Field(default_factory=SoilLower)
    microclimate: Microclimate = Field(default_factory=Microclimate)


class LabProfileIn(_Open):
    sample_date: Optional[str] = None
    texture_class: Optional[str] = None
    sand_pct: Optional[float] = None
    silt_pct: Optional[float] = None
    clay_pct: Optional[float] = None
    cec_meq: Optional[float] = None
    som_pct: Optional[float] = None
    caco3_pct: Optional[float] = None
    esp_pct: Optional[float] = None
    sar: Optional[float] = None
    bulk_density: Optional[float] = None
    water_table_m: Optional[float] = None
    water_ec_w: Optional[float] = None
    water_ph: Optional[float] = None
    water_hco3: Optional[float] = None
    water_boron_ppm: Optional[float] = None
    water_cl_ppm: Optional[float] = None
    lab_n_ppm: Optional[float] = None
    lab_p_ppm: Optional[float] = None
    lab_k_ppm: Optional[float] = None


class ZoneIn(_Open):
    name: Optional[str] = None
    governorate: Optional[str] = None
    area_feddan: Optional[float] = None
    irrigation_type: Optional[Literal["drip", "greenhouse", "pivot"]] = None
    season: Optional[Literal["auto", "shetwi", "seifi", "nili"]] = None
    active_crop_id: Optional[str] = None
    growth_stage: Optional[Literal["establishment", "vegetative", "flowering", "ripening"]] = None
    planting_date: Optional[str] = None
    expected_harvest_date: Optional[str] = None
    chill_hours_override: Optional[float] = None


class ManualSensors(_Open):
    vwc_upper: float
    vwc_lower: float
    matric_kpa: float
    soil_temp_c: float
    ece: float
    ph: float
    n: float
    p: float
    k: float
    orp_mv: float
    air_temp_c: float
    rh_pct: float
    o2_pct: Optional[float] = None
    par: Optional[float] = None
    leaf_wetness_pct: Optional[float] = None
    wind_ms: Optional[float] = None


class SimulatorPush(_Open):
    zone_id: int
    case_id: Optional[str] = None
    sensors: Optional[ManualSensors] = None
    lab: Optional[LabProfileIn] = None
    context: Optional[dict] = None


class SimulatorRandom(_Open):
    zone_id: int
    mode: str = "random"
    seed: Optional[int] = None


class ZoneRef(_Open):
    zone_id: int


class PrescriptionIn(_Open):
    zone_id: int
    crop_slug: Optional[str] = None
    stage: Optional[Literal["establishment", "vegetative", "flowering", "ripening"]] = None


class ZoneResetIn(_Open):
    readings: bool = True        # sensor readings (hardware + simulator) and device health
    alerts: bool = True
    prescriptions: bool = True
    lab: bool = True             # lab soil & water profiles and NPK calibration


class DeviceIn(_Open):
    zone_id: int
    device_id: str
    upper_depth_cm: int = 15
    lower_depth_cm: int = 35
