"""Weather forecast & uncertainty for Phase 17.

Forecast is uncertain; observed/forecast/simulated are distinct.
Uncertainty propagates via per-simulation weather trajectory.

No arbitrary Gaussian noise on every variable — documented stochastic components:
 - temperature drift N(0,0.2) * volatility
 - humidity N(0,1.0)
 - wind N(0,0.5)
 - rainfall uniform 0.5-3.0 on start, AR-like persistence for amount
All seeded via weather RNG stream.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from app.simulation.weather.state import WeatherState, EvidenceTier


class WeatherForecast(BaseModel):
    """Issued forecast for laps 1..L with confidence."""

    issue_time: str | None = None
    target_laps: int = 58
    predicted_states: list[WeatherState] = Field(default_factory=list)
    rain_probability: float = Field(default=0.0, ge=0, le=1)
    max_precipitation: float = Field(default=0.0, ge=0)
    temperature_range: tuple[float, float] = (20.0, 30.0)
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    confidence_decay_per_lap: float = Field(default=0.05, ge=0.01, le=0.2)

    model_config = {"use_enum_values": True}

    def get_for_lap(self, lap: int) -> WeatherState:
        if not self.predicted_states:
            return WeatherState.fallback_prior()
        if lap < len(self.predicted_states):
            return self.predicted_states[lap]
        return self.predicted_states[-1]

    def confidence_at(self, lap: int) -> float:
        return max(0.1, 1.0 - lap * self.confidence_decay_per_lap)


def build_forecast_from_states(states: list[WeatherState], issue_time: str | None = None) -> WeatherForecast:  # noqa: E501
    if not states:
        return WeatherForecast(predicted_states=[])
    max_precip = max((s.rainfall_mm_h or 0) for s in states)
    temps = [s.air_temperature_c for s in states if s.air_temperature_c is not None]
    rng = (min(temps), max(temps)) if temps else (20.0, 30.0)
    rain_prob = 1.0 if max_precip > 0 else 0.0
    return WeatherForecast(
        issue_time=issue_time,
        target_laps=len(states),
        predicted_states=states,
        rain_probability=rain_prob,
        max_precipitation=max_precip,
        temperature_range=rng,
        evidence_tier=EvidenceTier.CALIBRATED if len(states) > 10 else EvidenceTier.PRIOR_ONLY,
    )
