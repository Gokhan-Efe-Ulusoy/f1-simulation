"""RaceEngine v1.3.0 — Weather & Environmental State Engine, vectorized.

Extends v1.2.0 with modular weather integration:
  WeatherState(t) -> TrackEnvironment(t) -> TyreEnvironment(t) -> Grip(t) -> LapTime(t) -> Incident(t)  # noqa: E501

Preserves all prior guarantees, adds weather batch state (N,L) shared across drivers.
"""
from __future__ import annotations

import time
from typing import Any

from app.simulation.race_engine_v16 import TyreAwareRaceEngine
from app.simulation.scenario_v14 import Scenario
from app.simulation.weather.engine import WeatherEngine
from app.simulation.weather.state import WeatherState

RACEENGINE_VERSION = "raceengine-v1.3.0"
MODEL_VERSION = "0.4.0"
CALIBRATION_VERSION = "calibration-v1.0.0"
DATASET_VERSION = "f1-dataset-v1.1"
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"


class WeatherAwareRaceEngine(TyreAwareRaceEngine):
    """Weather-aware engine: adds environmental state to TyreAwareRaceEngine."""

    def __init__(
        self,
        calibration: str = CALIBRATION_VERSION,
        dataset: str = DATASET_VERSION,
        seed: int = 42,
        use_vectorized: bool = True,
        tyre_enabled: bool = True,
        weather_enabled: bool = True,
    ):
        super().__init__(calibration=calibration, dataset=dataset, seed=seed, use_vectorized=use_vectorized, tyre_enabled=tyre_enabled)  # noqa: E501
        self.version = RACEENGINE_VERSION
        self.model_version = MODEL_VERSION
        self.weather_enabled = weather_enabled
        self._weather_engines: dict[str, WeatherEngine] = {}

    def _get_weather_engine(self, as_of: str) -> WeatherEngine:
        if as_of not in self._weather_engines:
            self._weather_engines[as_of] = WeatherEngine(as_of=as_of, seed=self.seed)
        return self._weather_engines[as_of]

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed
        # Build calibration state via parent
        calib_state = self._build_calibration_state(scenario)

        # Weather availability: check scenario season
        weather_available = False
        weather_state: WeatherState | None = None
        if self.weather_enabled:
            try:
                we = self._get_weather_engine(scenario.as_of)
                weather_state = we.initial_state_for_scenario(scenario)
                # For modern 2023+ with OpenF1, LIMITED; else PRIOR_ONLY
                weather_available = True
            except Exception:
                weather_available = False
                weather_state = WeatherState.fallback_prior(timestamp=scenario.as_of)

        # Delegate to parent vectorized (which now includes weather trajectory)
        # It already handles weather via VectorizedMonteCarlo; we just add diagnostics
        result = super().simulate(scenario, simulations=simulations, seed=seed)

        # Enrich with weather metadata
        result["weather_model"] = {
            "version": WEATHER_MODEL_VERSION,
            "calibration_version": WEATHER_CALIBRATION_VERSION,
            "enabled": self.weather_enabled,
            "available": weather_available,
            "initial_state": weather_state.model_dump() if weather_state else None,
            "evidence_tier": weather_state.evidence_tier if weather_state else "PRIOR_ONLY",
            "per_field_tier": weather_state.per_field_tier if weather_state else {},
            "temporal": "persistent state with wetness(t+1)=wetness(t)+rain-drying bounded [0,1]",
            "correlation": "race-level shared across drivers (N,L) not per-driver",
        }
        # Fingerprint-relevant provenance
        result["provenance"]["weather_model_version"] = WEATHER_MODEL_VERSION
        result["provenance"]["weather_calibration_version"] = WEATHER_CALIBRATION_VERSION
        result["provenance"]["weather_enabled"] = self.weather_enabled
        result["provenance"]["model_version"] = MODEL_VERSION
        result["provenance"]["engine_version"] = RACEENGINE_VERSION
        # Ensure result fingerprint will change if weather config changes
        result["provenance"]["weather_seed"] = seed

        return result


# Alias
RaceEngine = WeatherAwareRaceEngine
