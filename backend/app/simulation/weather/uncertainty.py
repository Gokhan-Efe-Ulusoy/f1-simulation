"""Uncertainty propagation for weather.

Each stochastic component has documented rationale; no arbitrary global noise.
Distributions or intervals per variable where supported.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class WeatherUncertainty(BaseModel):
    """Per-variable uncertainty for propagation."""

    air_temperature_std: float = Field(default=1.0, ge=0, le=5)  # °C
    track_temperature_std: float = Field(default=1.5, ge=0, le=5)
    humidity_std: float = Field(default=3.0, ge=0, le=10)
    wind_speed_std: float = Field(default=0.5, ge=0, le=5)
    rainfall_std: float = Field(default=0.3, ge=0, le=5)  # mm/h for light rain
    wetness_std: float = Field(default=0.02, ge=0, le=0.2)

    # Confidence intervals (derived)
    # Used to add N(0, std) via weather RNG stream per lap

    def to_dict(self) -> dict:
        return self.model_dump()
