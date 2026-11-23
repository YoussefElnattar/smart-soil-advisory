"""FieldState: one place that fuses a sensor reading, the lab baseline and the
zone context into the derived values every engine module needs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..knowledge.crops import SEASON_MONTHS
from ..knowledge.soil import TEXTURES, default_bulk_density
from . import formulas as f


@dataclass
class FieldState:
    reading: dict            # flat sensor_readings row (see db.READING_COLUMNS)
    lab: dict                # lab_soil_profiles row (may be mostly empty)
    context: dict            # region, season, irrigation_type, month, chill_hours, crop_slug, stage
    history: list[dict] = field(default_factory=list)  # previous readings, newest first

    # ---- convenience accessors ------------------------------------------------
    def r(self, key: str):
        return self.reading.get(key)

    @property
    def texture(self) -> str:
        t = self.lab.get("texture_class") or "loam"
        return t if t in TEXTURES else "loam"

    @property
    def fc(self) -> float:
        return TEXTURES[self.texture]["fc"]

    @property
    def pwp(self) -> float:
        return TEXTURES[self.texture]["pwp"]

    @property
    def bulk_density(self) -> float:
        return self.lab.get("bulk_density") or default_bulk_density(self.texture)

    @property
    def month(self) -> int:
        if self.context.get("month"):
            return int(self.context["month"])
        ts = self.reading.get("time")
        if ts:
            try:
                return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).month
            except ValueError:
                pass
        return datetime.now(timezone.utc).month

    @property
    def seasons(self) -> set[str]:
        s = self.context.get("season")
        if s and s != "auto":
            return {s}
        return {name for name, months in SEASON_MONTHS.items() if self.month in months}

    @property
    def greenhouse(self) -> bool:
        return self.context.get("irrigation_type") == "greenhouse"

    @property
    def region(self) -> str | None:
        return self.context.get("region")

    # ---- derived values -------------------------------------------------------
    @property
    def ece(self) -> float | None:
        """Live root-zone ECe proxy = upper pore-water EC normalised to 25 °C."""
        return self.reading.get("ec25_upper")

    @property
    def ece_lower(self) -> float | None:
        return self.reading.get("ec25_lower")

    @property
    def awc_upper(self) -> float | None:
        v = self.reading.get("vwc_upper")
        return None if v is None else f.awc_pct(v, self.fc, self.pwp)

    @property
    def awc_lower(self) -> float | None:
        v = self.reading.get("vwc_lower")
        return None if v is None else f.awc_pct(v, self.fc, self.pwp)

    @property
    def vpd(self) -> float | None:
        t, rh = self.reading.get("air_temp_c"), self.reading.get("rh_pct")
        if t is None or rh is None:
            return None
        return f.vpd_kpa(t, rh)

    @property
    def dew_point_spread(self) -> float | None:
        t, rh = self.reading.get("air_temp_c"), self.reading.get("rh_pct")
        if t is None or rh is None:
            return None
        return t - f.dew_point_c(t, rh)

    @property
    def esp(self) -> float | None:
        if self.lab.get("esp_pct") is not None:
            return self.lab["esp_pct"]
        if self.lab.get("sar") is not None:
            return f.esp_from_sar(self.lab["sar"])
        return None

    @property
    def chill_hours(self) -> float | None:
        return self.context.get("chill_hours")

    def n_p_k(self) -> tuple[float | None, float | None, float | None, bool]:
        """Returns calibrated N, P, K if a lab calibration exists, else raw; plus flag."""
        cal = bool(self.reading.get("npk_calibrated"))
        if cal:
            return (self.reading.get("n_cal"), self.reading.get("p_cal"), self.reading.get("k_cal"), True)
        return (self.reading.get("n_ppm"), self.reading.get("p_ppm"), self.reading.get("k_ppm"), False)
