"""Model/simulation/configuration versioning (Phase 8).

Every completed simulation records these versions so historical
experiments can later be reproduced exactly.
"""
from __future__ import annotations

# Engine release line (bumped per phase)
SIMULATION_VERSION = "9.2.0"  # Phase 22 replay + counterfactual validation + pit-loss channel
RACEENGINE_VERSION = "raceengine-v2.2.0"  # Phase 22 replay-aware, pit-loss capable, vectorized
# Behavioral model bundle version — incremented for strategy pit-loss per spec 0.9
MODEL_VERSION = "0.9.0"
# Scenario model version
SCENARIO_MODEL_VERSION = "scenario-v1.0.0"
# Replay / counterfactual-experiment / sensitivity model versions (Phase 22)
REPLAY_MODEL_VERSION = "replay-v1.0.0"
COUNTERFACTUAL_MODEL_VERSION = "counterfactual-v1.0.0"
SENSITIVITY_MODEL_VERSION = "sensitivity-v1.0.0"
# Weather model version
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"
# Race Control model version
RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
# Strategy model version
STRATEGY_MODEL_VERSION = "strategy-v1.1.0"  # Phase 22: + pit_loss_seconds channel (default 0 = legacy)  # noqa: E501
# Setup model version
SETUP_MODEL_VERSION = "setup-v1.0.0"
# Configuration schema version
CONFIG_VERSION = "1.0.0"
