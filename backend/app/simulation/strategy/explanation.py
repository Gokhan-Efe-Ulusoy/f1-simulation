"""Explanation engine — derives reasons from evaluator inputs, no hallucination."""
from __future__ import annotations

from typing import Any

from app.simulation.strategy.state import StrategyState


class ExplanationEngine:
    """Maps strategy evaluation components to human-readable reasons."""

    COMPONENT_LABELS = {
        "TYRE_DEGRADATION": "tyre degradation increasing",
        "TYRE_PERFORMANCE": "tyre performance",
        "PIT_LOSS": "pit loss",
        "TRAFFIC": "traffic",
        "WEATHER": "weather",
        "RACE_CONTROL": "race control",
        "OPPONENT": "opponent",
        "FUEL": "fuel",
        "POSITION": "position",
        "UNCERTAINTY": "uncertainty",
    }

    def explain(
        self,
        state: StrategyState,
        chosen_strategy: Any,
        evaluation: dict[str, Any],
        pit_window: Any | None = None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        components: list[str] = []

        # Tyre
        if state.tyre_age > 18:
            reasons.append("tyre degradation increasing")
            components.append("TYRE_DEGRADATION")
        elif state.tyre_age > 12:
            reasons.append("tyre performance declining")
            components.append("TYRE_PERFORMANCE")

        # Pit loss / RC
        if state.race_control_phase == "SAFETY_CAR":
            reasons.append("pit loss currently reduced by Safety Car")
            components.append("PIT_LOSS")
            components.append("RACE_CONTROL")
        elif state.race_control_phase == "VSC":
            reasons.append("pit loss currently reduced by VSC")
            components.append("PIT_LOSS")
            components.append("RACE_CONTROL")

        # Traffic
        if state.gap_ahead > 0 and state.gap_ahead < 2:
            reasons.append("low traffic risk")
            components.append("TRAFFIC")
        elif state.gap_ahead > 0 and state.gap_ahead < 5:
            reasons.append("moderate traffic")

        # Weather
        rain_prob = state.forecast_summary.get("rain_prob_next_5", 0) if state.forecast_summary else 0  # noqa: E501
        if rain_prob > 0.3:
            reasons.append("uncertain weather crossover")
            components.append("WEATHER")
            components.append("UNCERTAINTY")
        elif state.rainfall == 0 and state.wetness < 0.1:
            reasons.append("current weather remains dry")
            components.append("WEATHER")

        # Fuel
        if state.fuel_remaining < 12:
            reasons.append("low fuel requires management")
            components.append("FUEL")

        # Stint/position
        if state.completed_pit_stops == 0 and state.laps_remaining < 30:
            reasons.append("track position preservation")
            components.append("POSITION")

        # Remaining uncertainty
        if evaluation.get("uncertainty", 0) > 0.25:
            components.append("UNCERTAINTY")

        # Filter to unique
        components = sorted(set(components))

        return {
            "reasons": reasons,
            "components": components,
            "evidence_tier": evaluation.get("evidence_tier", "PRIOR_ONLY"),
            "uncertainty": evaluation.get("uncertainty", 0.0),
        }
