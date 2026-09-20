"""RaceEngine v2.1.0 — Scenario & Counterfactual execution (Phase 21).

Thin layer over the Phase 20 setup-aware engine: no simulation behavior
changes, only scenario/counterfactual provenance stamping. The ScenarioEngine
(app.simulation.scenario) orchestrates baseline/counterfactual legs through
this engine with common random numbers.
"""
from __future__ import annotations

from typing import Any

from app.simulation.race_engine_v20 import SetupAwareRaceEngine
from app.simulation.scenario_v14 import Scenario

RACEENGINE_VERSION = "raceengine-v2.1.0"
MODEL_VERSION = "0.8.0"
SCENARIO_MODEL_VERSION = "scenario-v1.0.0"
CALIBRATION_VERSION = "calibration-v1.0.0"
DATASET_VERSION = "f1-dataset-v1.1"
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"
RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
STRATEGY_MODEL_VERSION = "strategy-v1.0.0"
SETUP_MODEL_VERSION = "setup-v1.0.0"


class ScenarioAwareRaceEngine(SetupAwareRaceEngine):
    """Scenario-aware engine: stamps scenario provenance, changes no dynamics."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.version = RACEENGINE_VERSION
        self.model_version = MODEL_VERSION

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed
        result = super().simulate(scenario, simulations=simulations, seed=seed)
        result["provenance"]["scenario_model_version"] = SCENARIO_MODEL_VERSION
        result["provenance"]["engine_version"] = RACEENGINE_VERSION
        result["provenance"]["model_version"] = MODEL_VERSION
        result["model_version"] = MODEL_VERSION
        result["scenario_model"] = {
            "version": SCENARIO_MODEL_VERSION,
            "scenario_type": getattr(scenario, "type", "historical"),
            "scenario_id": getattr(scenario, "scenario_id", ""),
            "evidence_tier": "PRIOR_ONLY",
        }
        return result


RaceEngine = ScenarioAwareRaceEngine
