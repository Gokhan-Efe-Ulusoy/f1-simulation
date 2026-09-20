from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class TeamOrderType(str):
    HOLD_POSITION = "HOLD_POSITION"
    LET_TEAMMATE_BY = "LET_TEAMMATE_BY"
    NO_ATTACK = "NO_ATTACK"
    ATTACK = "ATTACK"
    PIT_PRIORITY = "PIT_PRIORITY"
    STRATEGIC_SPLIT = "STRATEGIC_SPLIT"


@dataclass
class ChampionshipContext:
    """Minimal championship context for team decisions (Phase 7)."""
    points_difference: float = 0.0  # driver1 - driver2 (positive = driver1 ahead)
    remaining_races: int = 5
    constructor_position: int = 1
    driver_priority: str | None = None  # driver_id of priority driver, if any


@dataclass
class TeamOrderContext:
    """Context for team order evaluation."""
    team_id: str
    driver_id: str
    teammate_id: str
    position: int
    teammate_position: int
    gap: float  # seconds behind/ahead teammate (positive = behind)
    pace_difference: float  # driver pace - teammate pace (negative = faster)
    tyre_condition: float = 1.0
    teammate_tyre_condition: float = 1.0
    laps_remaining: int = 10
    championship: ChampionshipContext | None = None
    reliability_risk: float = 0.0


@dataclass
class TeamOrderDecision:
    """Result of team order evaluation."""
    order: str | None  # TeamOrderType or None
    target_driver_id: str | None = None
    reason: str = ""
    debug_info: dict[str, Any] = field(default_factory=dict)


class TeamOrderConfig(BaseModel):
    """Configuration for team order model (all coefficients documented)."""

    base_probability: float = Field(default=0.3, ge=0.0, le=1.0)  # base prob per evaluation
    gap_threshold: float = Field(default=1.0, ge=0.0, le=5.0)  # seconds
    pace_advantage_threshold: float = Field(default=0.3, ge=0.0, le=2.0)  # sec/lap
    championship_weight: float = Field(default=0.5, ge=0.0, le=2.0)  # unitless
    late_race_lap_threshold: int = Field(default=10, ge=1, le=70)  # laps remaining

    model_config = {"use_enum_values": True}


class TeamOrderModel:
    """Probabilistic, contextual team order model (no forced orders)."""

    def __init__(self, config: TeamOrderConfig | None = None):
        self.config = config or TeamOrderConfig()

    def evaluate(
        self, context: TeamOrderContext, rng: np.random.Generator
    ) -> TeamOrderDecision:
        """Evaluate whether a team order should be issued."""
        score = 0.0
        reasons: list[str] = []

        # Teammates close together
        if abs(context.gap) < self.config.gap_threshold:
            score += 0.3
            reasons.append("teammates_close")

        # Late race increases team-order likelihood
        if context.laps_remaining <= self.config.late_race_lap_threshold:
            score += 0.2
            reasons.append("late_race")

        # Championship context: protect priority driver
        champ = context.championship
        if champ and champ.driver_priority == context.teammate_id:
            score += self.config.championship_weight * 0.4
            reasons.append("championship_priority_teammate")
        elif champ and champ.driver_priority == context.driver_id:
            score -= 0.2
            reasons.append("championship_priority_self")

        # Pace difference: faster driver behind should attack or be let by
        if context.gap > 0 and context.pace_difference < -self.config.pace_advantage_threshold:
            score += 0.3
            reasons.append("faster_behind")

        prob = min(max(self.config.base_probability * 0.3 + score * 0.5, 0.0), 0.9)
        if rng.random() > prob:
            return TeamOrderDecision(order=None, reason="no_order:" + ",".join(reasons))

        # Choose order type
        if context.gap > 0 and context.pace_difference < -self.config.pace_advantage_threshold:
            order = TeamOrderType.ATTACK
        elif abs(context.gap) < 0.5 and context.laps_remaining <= self.config.late_race_lap_threshold:  # noqa: E501
            order = TeamOrderType.HOLD_POSITION
        else:
            order = TeamOrderType.NO_ATTACK

        return TeamOrderDecision(
            order=order,
            target_driver_id=context.teammate_id,
            reason=",".join(reasons),
            debug_info={"probability": prob},
        )
