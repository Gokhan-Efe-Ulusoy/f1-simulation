"""Opponent model — lightweight, prior-only, no future access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np


@dataclass
class OpponentPrediction:
    driver_id: str
    p_pit_next_lap: float
    p_stay_out: float
    p_switch_compound: dict[str, float]  # compound -> prob
    confidence: float
    evidence_tier: str = "PRIOR_ONLY"


class OpponentModel:
    """Estimates opponent behavior distributions, not deterministic future.

    Prior-only: P(pit_next) ~ Beta(2,20) mean 0.09 (~9% per lap when in window)
    """

    def __init__(self, base_pit_prob: float = 0.09):
        self.base = base_pit_prob

    def predict(
        self,
        opponent_state: dict[str, Any],
        race_control_phase: str = "GREEN",
        laps_remaining: int = 50,
    ) -> OpponentPrediction:
        did = opponent_state.get("driver_id", "OPP")
        gap = abs(float(opponent_state.get("gap_ahead", 5.0)))
        tyre_age = int(opponent_state.get("tyre_age", 10))

        # Simple prior: older tyres increase pit prob linearly
        age_factor = min(1.5, max(0.5, tyre_age / 15))
        # Race control SC increases pit prob
        rc_factor = 1.0
        if race_control_phase == "SAFETY_CAR":
            rc_factor = 3.0
        elif race_control_phase == "VSC":
            rc_factor = 2.0
        elif race_control_phase in ("YELLOW", "DOUBLE_YELLOW"):
            rc_factor = 1.5

        # Laps remaining small => higher prob (must pit)
        laps_factor = 1.0 if laps_remaining > 15 else 1.8

        p_pit = min(0.6, self.base * age_factor * rc_factor * laps_factor)

        # Compound switch prob uniform among non-current (prior)
        compounds = ["soft", "medium", "hard"]
        cur = opponent_state.get("compound", "medium")
        others = [c for c in compounds if c != cur]
        p_switch = {c: (1.0 / len(others) * p_pit) if others else 0 for c in others}
        # Stay out complementary
        p_stay = 1.0 - p_pit

        # Confidence based on evidence tier (always PRIOR_ONLY) and gap observability
        confidence = 0.4 if gap < 2 else 0.25  # closer more observable

        return OpponentPrediction(
            driver_id=did,
            p_pit_next_lap=float(p_pit),
            p_stay_out=float(p_stay),
            p_switch_compound=p_switch,
            confidence=confidence,
            evidence_tier="PRIOR_ONLY",
        )

    def batch_predict(
        self, opponent_states: list[dict[str, Any]], race_control_phase: str = "GREEN", laps_remaining: int = 50  # noqa: E501
    ) -> list[OpponentPrediction]:
        return [self.predict(o, race_control_phase, laps_remaining) for o in opponent_states]
