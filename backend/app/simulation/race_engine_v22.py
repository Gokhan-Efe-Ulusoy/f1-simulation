"""RaceEngine v2.2.0 — Historical Replay & Counterfactual Validation (Phase 22).

Thin layer over the Phase 21 scenario-aware engine: no simulation behavior
changes except the explicitly versioned strategy pit-loss channel
(`strategy.pit_loss_seconds`, default 0.0 = legacy exact). Adds replay /
counterfactual / sensitivity provenance stamping.

The replay package (app.simulation.replay) orchestrates baseline replay,
counterfactual replay, sensitivity sweeps and sanity checks through this
engine with common random numbers.
"""
from __future__ import annotations

from typing import Any

from app.simulation.race_engine_v21 import ScenarioAwareRaceEngine
from app.simulation.scenario_v14 import Scenario

RACEENGINE_VERSION = "raceengine-v2.2.0"
MODEL_VERSION = "0.9.0"
SCENARIO_MODEL_VERSION = "scenario-v1.0.0"
REPLAY_MODEL_VERSION = "replay-v1.0.0"
COUNTERFACTUAL_MODEL_VERSION = "counterfactual-v1.0.0"
SENSITIVITY_MODEL_VERSION = "sensitivity-v1.0.0"
CALIBRATION_VERSION = "calibration-v1.0.0"
DATASET_VERSION = "f1-dataset-v1.1"
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"
RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
STRATEGY_MODEL_VERSION = "strategy-v1.1.0"
SETUP_MODEL_VERSION = "setup-v1.0.0"


class ReplayAwareRaceEngine(ScenarioAwareRaceEngine):
    """Replay-aware engine: stamps replay provenance, changes no dynamics."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.version = RACEENGINE_VERSION
        self.model_version = MODEL_VERSION

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed
        result = super().simulate(scenario, simulations=simulations, seed=seed)
        result["provenance"]["replay_model_version"] = REPLAY_MODEL_VERSION
        result["provenance"]["counterfactual_model_version"] = COUNTERFACTUAL_MODEL_VERSION
        result["provenance"]["sensitivity_model_version"] = SENSITIVITY_MODEL_VERSION
        result["provenance"]["strategy_model_version"] = STRATEGY_MODEL_VERSION
        result["provenance"]["engine_version"] = RACEENGINE_VERSION
        result["provenance"]["model_version"] = MODEL_VERSION
        result["model_version"] = MODEL_VERSION
        result["replay_model"] = {
            "version": REPLAY_MODEL_VERSION,
            "counterfactual_version": COUNTERFACTUAL_MODEL_VERSION,
            "sensitivity_version": SENSITIVITY_MODEL_VERSION,
            "evidence_tier": "PRIOR_ONLY",
        }
        sm = result.get("strategy_model")
        if isinstance(sm, dict):
            sm["version"] = STRATEGY_MODEL_VERSION
        return result


RaceEngine = ReplayAwareRaceEngine
