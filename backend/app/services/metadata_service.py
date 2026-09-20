"""Phase 28 — Metadata service (thin wrapper over version constants)."""

from __future__ import annotations

from app.simulation.version import (
    CONFIG_VERSION,
    COUNTERFACTUAL_MODEL_VERSION,
    MODEL_VERSION,
    RACE_CONTROL_MODEL_VERSION,
    RACE_CONTROL_POLICY_VERSION,
    RACEENGINE_VERSION,
    REPLAY_MODEL_VERSION,
    SCENARIO_MODEL_VERSION,
    SENSITIVITY_MODEL_VERSION,
    SETUP_MODEL_VERSION,
    SIMULATION_VERSION,
    STRATEGY_MODEL_VERSION,
    WEATHER_CALIBRATION_VERSION,
    WEATHER_MODEL_VERSION,
)


def get_metadata() -> dict:
    return {
        "api_version": "v1",
        "dataset_version": "f1-dataset-v1.3",
        "dataset_hash": "sha256:canonical-races-v1.3",
        "calibration_version": "calibration-v1.0.0",
        "tyre_version": "tyre-v1.0.0",
        "tyre_model_version": "tyre-v1.0.0",
        "weather_version": WEATHER_MODEL_VERSION,
        "weather_calibration_version": WEATHER_CALIBRATION_VERSION,
        "race_control_version": RACE_CONTROL_MODEL_VERSION,
        "race_control_policy_version": RACE_CONTROL_POLICY_VERSION,
        "strategy_version": STRATEGY_MODEL_VERSION,
        "setup_version": SETUP_MODEL_VERSION,
        "race_engine_version": RACEENGINE_VERSION,
        "model_version": MODEL_VERSION,
        "simulation_version": SIMULATION_VERSION,
        "config_version": CONFIG_VERSION,
        "scenario_model_version": SCENARIO_MODEL_VERSION,
        "replay_model_version": REPLAY_MODEL_VERSION,
        "counterfactual_model_version": COUNTERFACTUAL_MODEL_VERSION,
        "sensitivity_model_version": SENSITIVITY_MODEL_VERSION,
        "evidence_tiers": {
            "fuel": "NON_IDENTIFIABLE",
            "tyre_historical": "NON_IDENTIFIABLE",
            "tyre_modern": "LIMITED",
            "strategy": "PRIOR_ONLY",
            "setup": "PRIOR_ONLY",
            "weather_historical": "PRIOR_ONLY",
            "race_control_historical": "PRIOR_ONLY",
            "driver": "LIMITED",
            "circuit": "LIMITED",
            "constructor": "LIMITED",
        },
        "provenance": {
            "dataset": "f1-dataset-v1.3",
            "note": "Phase 27 retained production model; no calibration promotion in Phase 28",
        },
    }
