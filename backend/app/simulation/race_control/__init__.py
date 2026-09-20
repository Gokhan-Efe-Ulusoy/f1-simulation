"""Race Control package for Phase 18."""

from app.simulation.race_control.models import (
    DriverControlState,
    EvidenceTier,
    IncidentSeverity,
    RaceControlSnapshot,
    RaceControlState,
    RaceEvent,
    RaceEventType,
    SectorControlState,
    TrackControlState,
)
from app.simulation.race_control.state_machine import RaceControlStateMachine, VALID_TRANSITIONS, PRIORITY, is_valid_transition  # noqa: E501
from app.simulation.race_control.policy import RaceControlPolicy, DEFAULT_RACE_CONTROL_POLICY
from app.simulation.race_control.neutralisation import NeutralisationFactors, NEUTRALISATION_TABLE, factors_for, compress_gaps_step  # noqa: E501
from app.simulation.race_control.rng import race_control_rng, deterministic_event_id
from app.simulation.race_control.engine import RaceControlEngine
from app.simulation.race_control.kernels import PHASE_GREEN, PHASE_YELLOW, PHASE_DOUBLE_YELLOW, PHASE_VSC, PHASE_SAFETY_CAR, PHASE_RED_FLAG, PHASE_FORMATION_LAP, PHASE_START, PHASE_RESTART, PHASE_CHEQUERED_FLAG, PHASE_RACE_SUSPENDED, PHASE_RACE_RESUMED, gaps_compression_kernel, pace_control_kernel  # noqa: E501

__all__ = [
    "EvidenceTier",
    "RaceControlState",
    "TrackControlState",
    "SectorControlState",
    "DriverControlState",
    "RaceEventType",
    "RaceEvent",
    "RaceControlSnapshot",
    "IncidentSeverity",
    "RaceControlStateMachine",
    "VALID_TRANSITIONS",
    "PRIORITY",
    "is_valid_transition",
    "RaceControlPolicy",
    "DEFAULT_RACE_CONTROL_POLICY",
    "NeutralisationFactors",
    "NEUTRALISATION_TABLE",
    "factors_for",
    "compress_gaps_step",
    "race_control_rng",
    "deterministic_event_id",
    "RaceControlEngine",
    "PHASE_GREEN",
    "PHASE_YELLOW",
    "PHASE_DOUBLE_YELLOW",
    "PHASE_VSC",
    "PHASE_SAFETY_CAR",
    "PHASE_RED_FLAG",
    "PHASE_FORMATION_LAP",
    "PHASE_START",
    "PHASE_RESTART",
    "PHASE_CHEQUERED_FLAG",
    "PHASE_RACE_SUSPENDED",
    "PHASE_RACE_RESUMED",
    "gaps_compression_kernel",
    "pace_control_kernel",
]

RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
