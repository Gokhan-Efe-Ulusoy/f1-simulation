"""Race Control domain models — enums, events, state.

Evidence tiers follow project convention: OBSERVED / CALIBRATED / ESTIMATED / PRIOR_ONLY / NON_IDENTIFIABLE.  # noqa: E501
All race-control coefficients are PRIOR_ONLY unless otherwise calibrated (none are).
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceTier(str, Enum):
    OBSERVED = "OBSERVED"
    CALIBRATED = "CALIBRATED"
    ESTIMATED = "ESTIMATED"
    PRIOR_ONLY = "PRIOR_ONLY"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"


# ---------------------------------------------------------------------------
# Race control phases / states — explicit enums, not free strings
# ---------------------------------------------------------------------------
class RaceControlState(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    VSC = "VSC"
    SAFETY_CAR = "SAFETY_CAR"
    RED_FLAG = "RED_FLAG"
    FORMATION_LAP = "FORMATION_LAP"
    START = "START"
    RESTART = "RESTART"
    CHEQUERED_FLAG = "CHEQUERED_FLAG"
    RACE_SUSPENDED = "RACE_SUSPENDED"
    RACE_RESUMED = "RACE_RESUMED"


class TrackControlState(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    VSC = "VSC"
    SAFETY_CAR = "SAFETY_CAR"
    RED_FLAG = "RED_FLAG"


class SectorControlState(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"


class DriverControlState(str, Enum):
    RACING = "RACING"
    YELLOW_AFFECTED = "YELLOW_AFFECTED"
    VSC_CONTROLLED = "VSC_CONTROLLED"
    SC_CONTROLLED = "SC_CONTROLLED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


# ---------------------------------------------------------------------------
# Race events
# ---------------------------------------------------------------------------
class RaceEventType(str, Enum):
    SPIN = "SPIN"
    LOCKUP = "LOCKUP"
    OFF_TRACK = "OFF_TRACK"
    COLLISION = "COLLISION"
    DAMAGE = "DAMAGE"
    RETIREMENT = "RETIREMENT"
    DEBRIS = "DEBRIS"
    STOPPED_CAR = "STOPPED_CAR"
    OBSTRUCTION = "OBSTRUCTION"
    RAIN_INTENSIFICATION = "RAIN_INTENSIFICATION"
    POOR_VISIBILITY = "POOR_VISIBILITY"
    TRACK_BLOCKAGE = "TRACK_BLOCKAGE"
    MARSHAL_INTERVENTION = "MARSHAL_INTERVENTION"
    YELLOW_FLAG = "YELLOW_FLAG"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    VSC_DEPLOYED = "VSC_DEPLOYED"
    VSC_ENDING = "VSC_ENDING"
    SAFETY_CAR_DEPLOYED = "SAFETY_CAR_DEPLOYED"
    SAFETY_CAR_ENDING = "SAFETY_CAR_ENDING"
    RED_FLAG = "RED_FLAG"
    RESTART = "RESTART"
    RACE_RESUMED = "RACE_RESUMED"
    CHEQUERED_FLAG = "CHEQUERED_FLAG"
    FORMATION_LAP = "FORMATION_LAP"
    START = "START"


class IncidentSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class RaceEvent(BaseModel):
    """Generic deterministic race event."""

    id: str
    event_type: RaceEventType
    lap: int
    timestamp: float = 0.0
    track_position: float | None = None
    sector: int = 0  # 0-based, -1 = global
    driver_ids: list[str] = Field(default_factory=list)
    severity: IncidentSeverity | None = None
    duration: int | None = None  # laps
    trigger: str | None = None
    cause: str | None = None
    confidence: float = 1.0
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    resolved: bool = False
    parent_event_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# RaceControlState — immutable / versioned snapshot per lap (race-level)
# ---------------------------------------------------------------------------
class RaceControlSnapshot(BaseModel):
    """Immutable race-control state at a given lap.

    This is the (N,L) shared state. Sector and driver variants are derived.
    """

    phase: RaceControlState = RaceControlState.GREEN
    control_state: TrackControlState = TrackControlState.GREEN
    lap: int = 0
    timestamp: float = 0.0
    # Per-sector states (len == num_sectors, default 3)
    sector_states: list[SectorControlState] = Field(default_factory=lambda: [SectorControlState.GREEN] * 3)  # noqa: E501
    active_event_ids: list[str] = Field(default_factory=list)
    safety_car_active: bool = False
    vsc_active: bool = False
    red_flag_active: bool = False
    restart_pending: bool = False
    formation_lap: bool = False
    race_suspended: bool = False
    race_resumed: bool = False
    double_yellow_active: bool = False
    yellow_sectors: list[int] = Field(default_factory=list)  # indices where yellow
    sc_lap_count: int = 0
    vsc_lap_count: int = 0
    red_flag_lap: int | None = None
    reason: str | None = None
    source_event_id: str | None = None
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    # Neutralisation factors active this lap
    pace_factor: float = 1.0
    overtake_factor: float = 1.0
    battle_factor: float = 1.0
    incident_factor: float = 1.0
    pit_cost_factor: float = 1.0
    # DRS
    drs_enabled: bool = True
    # Version
    version: str = "racecontrol-v1.0.0"

    model_config = {"use_enum_values": True}

    def is_neutralised(self) -> bool:
        return self.phase in (
            RaceControlState.VSC,
            RaceControlState.SAFETY_CAR,
            RaceControlState.RED_FLAG,
            RaceControlState.RACE_SUSPENDED,
        )

    def allows_overtaking(self) -> bool:
        return self.phase in (RaceControlState.GREEN, RaceControlState.RESTART)

    def allows_drs(self) -> bool:
        return self.drs_enabled and self.phase == RaceControlState.GREEN
