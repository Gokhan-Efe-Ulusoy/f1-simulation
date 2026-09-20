"""RaceEngine v1.5.0 — Advanced Strategy & Decision Engine, vectorized.

Extends v1.4.0 (race control) with strategy decision layer.
"""
from __future__ import annotations

from typing import Any

from app.simulation.race_engine_v18 import RaceControlAwareRaceEngine
from app.simulation.scenario_v14 import Scenario

RACEENGINE_VERSION = "raceengine-v1.5.0"
MODEL_VERSION = "0.6.0"
CALIBRATION_VERSION = "calibration-v1.0.0"
DATASET_VERSION = "f1-dataset-v1.1"
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"
RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
STRATEGY_MODEL_VERSION = "strategy-v1.0.0"


class StrategyAwareRaceEngine(RaceControlAwareRaceEngine):
    """Strategy-aware engine: adds strategy decision layer."""

    def __init__(
        self,
        calibration: str = CALIBRATION_VERSION,
        dataset: str = DATASET_VERSION,
        seed: int = 42,
        use_vectorized: bool = True,
        tyre_enabled: bool = True,
        weather_enabled: bool = True,
        race_control_enabled: bool = True,
        strategy_enabled: bool = True,
    ):
        super().__init__(
            calibration=calibration,
            dataset=dataset,
            seed=seed,
            use_vectorized=use_vectorized,
            tyre_enabled=tyre_enabled,
            weather_enabled=weather_enabled,
            race_control_enabled=race_control_enabled,
        )
        self.version = RACEENGINE_VERSION
        self.model_version = MODEL_VERSION
        self.strategy_enabled = strategy_enabled

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed

        # Strategy mods via scenario hypothetical_modifiers.strategy
        strategy_enabled_local = self.strategy_enabled
        try:
            mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
            strat = mods.get("strategy", {}) if isinstance(mods.get("strategy"), dict) else {}
            if strat.get("enabled") is False or mods.get("strategy_enabled") is False:
                strategy_enabled_local = False
            elif strat.get("enabled") is True or mods.get("strategy_enabled") is True:
                strategy_enabled_local = True
        except:
            pass

        if not strategy_enabled_local:
            if not hasattr(scenario, "hypothetical_modifiers") or scenario.hypothetical_modifiers is None:  # noqa: E501
                scenario.hypothetical_modifiers = {}
            if "strategy" not in scenario.hypothetical_modifiers or not isinstance(scenario.hypothetical_modifiers["strategy"], dict):  # noqa: E501
                scenario.hypothetical_modifiers["strategy"] = {}
            scenario.hypothetical_modifiers["strategy"]["enabled"] = False

        result = super().simulate(scenario, simulations=simulations, seed=seed)

        # Ensure strategy provenance
        if "strategy" not in result:
            # synthesize fallback via DecisionEngine for small N
            try:
                from app.simulation.strategy.decision_engine import DecisionEngine
                from app.simulation.strategy.state import build_strategy_state_from_driver

                # Create dummy decision for diagnostics (leakage-safe example)
                dummy_state = build_strategy_state_from_driver(
                    driver_id="dummy",
                    lap=1,
                    position=5,
                    gap_ahead=1.2,
                    gap_behind=0.8,
                    current_compound="medium",
                    tyre_age=5,
                    fuel_remaining=80,
                    race_control_phase="GREEN",
                    laps_remaining=result["summary"]["simulations"] if "summary" in result else 58,
                )
                eng = DecisionEngine(as_of=scenario.as_of, seed=seed)
                dec = eng.decide(dummy_state, seed=seed)
                strategy_diag = {
                    "enabled": strategy_enabled_local,
                    "version": STRATEGY_MODEL_VERSION,
                    "evidence_tier": "PRIOR_ONLY",
                    "decision_example": dec.model_dump() if hasattr(dec, "model_dump") else dec,
                    "max_candidates": eng.candidate_gen.max_candidates,
                }
                result["strategy"] = strategy_diag
                result["strategy_decision_example"] = dec.model_dump() if hasattr(dec, "model_dump") else dec  # noqa: E501
            except Exception as e:
                result["strategy"] = {
                    "enabled": strategy_enabled_local,
                    "version": STRATEGY_MODEL_VERSION,
                    "evidence_tier": "PRIOR_ONLY",
                    "error": str(e),
                }
            result["provenance"]["strategy_model_version"] = STRATEGY_MODEL_VERSION
            result["provenance"]["strategy_enabled"] = strategy_enabled_local
        else:
            result["provenance"]["strategy_model_version"] = STRATEGY_MODEL_VERSION
            result["provenance"]["strategy_enabled"] = strategy_enabled_local

        result["provenance"]["engine_version"] = RACEENGINE_VERSION
        result["provenance"]["model_version"] = MODEL_VERSION
        result["model_version"] = MODEL_VERSION
        result["strategy_model"] = {
            "version": STRATEGY_MODEL_VERSION,
            "enabled": strategy_enabled_local,
            "evidence_tier": "PRIOR_ONLY",
        }
        return result


RaceEngine = StrategyAwareRaceEngine
