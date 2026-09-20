"""Explicit state machine for Race Control — no scattered ifs."""
from __future__ import annotations

from app.simulation.race_control.models import RaceControlState


# Valid transitions — exhaustive, documents allowed edges.
# Key: current -> set of allowed next
VALID_TRANSITIONS: dict[RaceControlState, set[RaceControlState]] = {
    RaceControlState.GREEN: {
        RaceControlState.YELLOW,
        RaceControlState.DOUBLE_YELLOW,
        RaceControlState.VSC,
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
        RaceControlState.FORMATION_LAP,
        RaceControlState.START,
        RaceControlState.CHEQUERED_FLAG,
    },
    RaceControlState.YELLOW: {
        RaceControlState.GREEN,
        RaceControlState.DOUBLE_YELLOW,
        RaceControlState.VSC,
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
    },
    RaceControlState.DOUBLE_YELLOW: {
        RaceControlState.GREEN,
        RaceControlState.VSC,
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
    },
    RaceControlState.VSC: {
        RaceControlState.GREEN,
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
        RaceControlState.RESTART,
    },
    RaceControlState.SAFETY_CAR: {
        RaceControlState.RESTART,
        RaceControlState.RED_FLAG,
        RaceControlState.GREEN,  # direct if lap clears without explicit RESTART (tolerant)
    },
    RaceControlState.RED_FLAG: {
        RaceControlState.RESTART,
        RaceControlState.RACE_SUSPENDED,
        RaceControlState.RACE_RESUMED,
        RaceControlState.CHEQUERED_FLAG,
        RaceControlState.GREEN,  # restart path collapses to GREEN after RESTART
    },
    RaceControlState.RACE_SUSPENDED: {
        RaceControlState.RACE_RESUMED,
        RaceControlState.RESTART,
        RaceControlState.CHEQUERED_FLAG,
    },
    RaceControlState.RACE_RESUMED: {
        RaceControlState.RESTART,
        RaceControlState.GREEN,
    },
    RaceControlState.RESTART: {
        RaceControlState.GREEN,
        RaceControlState.YELLOW,  # incident on restart
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
    },
    RaceControlState.FORMATION_LAP: {
        RaceControlState.START,
        RaceControlState.GREEN,
        RaceControlState.RED_FLAG,
    },
    RaceControlState.START: {
        RaceControlState.GREEN,
        RaceControlState.YELLOW,
        RaceControlState.SAFETY_CAR,
        RaceControlState.RED_FLAG,
    },
    RaceControlState.CHEQUERED_FLAG: set(),  # terminal
}

# Event priority for deterministic ordering when multiple deploy simultaneously.
# Higher value = higher precedence.
PRIORITY: dict[RaceControlState, int] = {
    RaceControlState.RED_FLAG: 100,
    RaceControlState.RACE_SUSPENDED: 95,
    RaceControlState.SAFETY_CAR: 80,
    RaceControlState.VSC: 60,
    RaceControlState.DOUBLE_YELLOW: 40,
    RaceControlState.YELLOW: 30,
    RaceControlState.RESTART: 90,  # restart ending SC has high priority to clear
    RaceControlState.GREEN: 10,
    RaceControlState.FORMATION_LAP: 15,
    RaceControlState.START: 15,
    RaceControlState.CHEQUERED_FLAG: 110,
    RaceControlState.RACE_RESUMED: 92,
}


def is_valid_transition(frm: RaceControlState, to: RaceControlState) -> bool:
    if frm == to:
        return True  # staying is allowed
    return to in VALID_TRANSITIONS.get(frm, set())


def assert_valid_transition(frm: RaceControlState, to: RaceControlState) -> None:
    if not is_valid_transition(frm, to):
        raise ValueError(f"Invalid race-control transition {frm.value} -> {to.value}")


def resolve_highest_priority(candidates: list[RaceControlState]) -> RaceControlState:
    """Deterministic precedence resolution: highest priority wins; tie -> lexical order."""
    if not candidates:
        return RaceControlState.GREEN
    # sort by (-priority, value) stable
    ranked = sorted(candidates, key=lambda s: (-PRIORITY.get(s, 0), s.value))
    return ranked[0]


class RaceControlStateMachine:
    """Stateful machine wrapper — holds current and enforces transitions."""

    def __init__(self, initial: RaceControlState = RaceControlState.GREEN):
        self.current = initial
        self.history: list[tuple[int, RaceControlState, RaceControlState]] = []

    def can_transition(self, target: RaceControlState) -> bool:
        return is_valid_transition(self.current, target)

    def transition(self, target: RaceControlState, lap: int | None = None) -> RaceControlState:
        assert_valid_transition(self.current, target)
        prev = self.current
        self.current = target
        if lap is not None:
            self.history.append((lap, prev, target))
        return self.current

    def force(self, target: RaceControlState, lap: int | None = None) -> RaceControlState:
        """Force without validation — for RACE_SUSPENDED internal use only."""
        prev = self.current
        self.current = target
        if lap is not None:
            self.history.append((lap, prev, target))
        return self.current
