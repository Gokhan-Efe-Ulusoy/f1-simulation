"""Strategy actions — explicit, serializable, deterministic."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CONTINUE = "CONTINUE"
    PIT = "PIT"
    CHANGE_COMPOUND = "CHANGE_COMPOUND"
    STAY_OUT = "STAY_OUT"
    PUSH = "PUSH"
    MANAGE_TYRES = "MANAGE_TYRES"
    MANAGE_FUEL = "MANAGE_FUEL"
    ATTACK = "ATTACK"
    DEFEND = "DEFEND"
    PREPARE_RESTART = "PREPARE_RESTART"


class StrategyAction(BaseModel):
    """Base action — all actions are serializable."""

    action_type: ActionType
    evidence_tier: str = "PRIOR_ONLY"
    reasoning: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ContinueAction(StrategyAction):
    action_type: ActionType = ActionType.CONTINUE
    note: str = "stay out, continue current stint"


class PitAction(StrategyAction):
    """Pit stop action — contains lap and compound."""

    action_type: ActionType = ActionType.PIT
    pit_lap: int
    target_compound: str
    expected_stint_length: int | None = None
    reason: str = "scheduled"
    pit_window: list[int] | None = None  # [earliest, latest]

    model_config = {"use_enum_values": True}


class StayOutAction(StrategyAction):
    action_type: ActionType = ActionType.STAY_OUT
    reason: str = "outside window or traffic"


class ManageTyresAction(StrategyAction):
    action_type: ActionType = ActionType.MANAGE_TYRES
    target_pace_delta: float = 0.3


class ManageFuelAction(StrategyAction):
    action_type: ActionType = ActionType.MANAGE_FUEL
    target_mode: str = "lean"


class AttackAction(StrategyAction):
    action_type: ActionType = ActionType.ATTACK
    target_driver_id: str | None = None


class DefendAction(StrategyAction):
    action_type: ActionType = ActionType.DEFEND
    attacker_id: str | None = None
