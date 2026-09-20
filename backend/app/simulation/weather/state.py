"""Canonical WeatherState for Phase 17.

Strongly typed, units explicit, ranges validated, deterministic serialization,
evidence tier per-variable, provenance-aware.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceTier(str, Enum):
    OBSERVED = "OBSERVED"
    CALIBRATED = "CALIBRATED"
    ESTIMATED = "ESTIMATED"
    PRIOR_ONLY = "PRIOR_ONLY"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"


class RainfallIntensity(str, Enum):
    NONE = "NONE"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"


class WeatherEvidence(BaseModel):
    """Per-field provenance."""

    value: Any
    source: str = "unknown"
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    timestamp: str | None = None
    race_id: str | None = None
    session_id: str | None = None


class WeatherState(BaseModel):
    """Canonical weather state at time t.

    All temperatures in Celsius (°C), pressure in hPa, wind in m/s,
    direction in degrees 0-360, rainfall in mm/h, wetness 0-1.
    """

    # Timestamp (ISO8601) — for historical observations
    timestamp: str | None = None

    # Core thermodynamics
    air_temperature_c: float | None = Field(default=None, ge=-10, le=50)
    track_temperature_c: float | None = Field(default=None, ge=-5, le=65)
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    pressure_hpa: float | None = Field(default=None, ge=900, le=1100)

    # Wind
    wind_speed_mps: float | None = Field(default=None, ge=0, le=50)
    wind_direction_deg: float | None = Field(default=None, ge=0, le=360)

    # Precipitation
    rainfall_mm_h: float | None = Field(default=None, ge=0, le=100)
    rainfall_intensity: RainfallIntensity = RainfallIntensity.NONE
    rain_intensity: RainfallIntensity | None = None  # alias for compat

    # Track surface
    track_wetness: float = Field(default=0.0, ge=0, le=1)  # 0 dry, 1 saturated

    # Regime (derived)
    weather_regime: str | None = None  # filled by regime.py

    # Optics / safety
    visibility_km: float | None = Field(default=None, ge=0, le=20)
    cloud_cover_pct: float | None = Field(default=None, ge=0, le=100)

    # Evidence tiers per variable
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    per_field_tier: dict[str, EvidenceTier] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def model_post_init(self, __context: Any) -> None:
        # Normalize alias
        if self.rain_intensity is not None and self.rainfall_intensity == RainfallIntensity.NONE:
            self.rainfall_intensity = self.rain_intensity
        # Derive intensity from rainfall if not set
        if self.rainfall_mm_h is not None:
            self.rainfall_intensity = self._intensity_from_rainfall(self.rainfall_mm_h)
        # Derive regime will be set by caller via WeatherRegime.derive
        # Ensure wetness bounds
        self.track_wetness = max(0.0, min(1.0, float(self.track_wetness)))

    @staticmethod
    def _intensity_from_rainfall(mm_h: float) -> RainfallIntensity:
        if mm_h is None or mm_h <= 0.0:
            return RainfallIntensity.NONE
        if mm_h < 2.5:
            return RainfallIntensity.LIGHT
        if mm_h < 7.5:
            return RainfallIntensity.MODERATE
        return RainfallIntensity.HEAVY

    def get_grip_multiplier(self) -> float:
        """Grip factor from wetness (same curve as legacy WeatherState)."""
        w = self.track_wetness
        if w <= 0.05:
            return 1.0
        elif w <= 0.2:
            return 0.95 - w * 0.2
        elif w <= 0.5:
            return 0.91 - (w - 0.2) * 0.4
        elif w <= 0.8:
            return 0.79 - (w - 0.5) * 0.5
        else:
            return max(0.4, 0.64 - (w - 0.8) * 1.2)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_observed(
        cls,
        air_temperature_c: float | None,
        track_temperature_c: float | None,
        humidity_pct: float | None,
        pressure_hpa: float | None,
        wind_speed_mps: float | None,
        wind_direction_deg: float | None,
        rainfall_mm_h: float | None,
        track_wetness: float = 0.0,
        timestamp: str | None = None,
        race_id: str | None = None,
        session_id: str | None = None,
        source: str = "openf1",
    ) -> "WeatherState":
        tiers: dict[str, EvidenceTier] = {}
        for k, v in {
            "air_temperature_c": air_temperature_c,
            "track_temperature_c": track_temperature_c,
            "humidity_pct": humidity_pct,
            "pressure_hpa": pressure_hpa,
            "wind_speed_mps": wind_speed_mps,
            "wind_direction_deg": wind_direction_deg,
            "rainfall_mm_h": rainfall_mm_h,
            "track_wetness": track_wetness,
        }.items():
            tiers[k] = EvidenceTier.OBSERVED if v is not None else EvidenceTier.PRIOR_ONLY
        # If rainfall is 0, intensity NONE is OBSERVED; else OBSERVED
        return cls(
            timestamp=timestamp,
            air_temperature_c=air_temperature_c,
            track_temperature_c=track_temperature_c,
            humidity_pct=humidity_pct,
            pressure_hpa=pressure_hpa,
            wind_speed_mps=wind_speed_mps,
            wind_direction_deg=wind_direction_deg,
            rainfall_mm_h=rainfall_mm_h if rainfall_mm_h is not None else 0.0,
            track_wetness=float(track_wetness) if track_wetness is not None else 0.0,
            evidence_tier=EvidenceTier.OBSERVED,
            per_field_tier=tiers,
            provenance={"source": source, "race_id": race_id, "session_id": session_id, "timestamp": timestamp},  # noqa: E501
            visibility_km=1.0,
        )

    @classmethod
    def fallback_prior(cls, timestamp: str | None = None) -> "WeatherState":
        """Conservative dry prior when no observation."""
        return cls(
            timestamp=timestamp,
            air_temperature_c=25.0,
            track_temperature_c=35.0,
            humidity_pct=60.0,
            pressure_hpa=1013.0,
            wind_speed_mps=3.0,
            wind_direction_deg=0.0,
            rainfall_mm_h=0.0,
            track_wetness=0.0,
            evidence_tier=EvidenceTier.PRIOR_ONLY,
            per_field_tier={k: EvidenceTier.PRIOR_ONLY for k in ["air_temperature_c","track_temperature_c","humidity_pct","pressure_hpa","wind_speed_mps","wind_direction_deg","rainfall_mm_h","track_wetness"]},  # noqa: E501
            provenance={"source": "prior", "note": "fallback dry prior"},
            visibility_km=1.0,
        )
