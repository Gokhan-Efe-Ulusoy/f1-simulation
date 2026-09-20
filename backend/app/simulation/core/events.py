from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of simulation events."""

    # Race lifecycle
    RACE_STARTED = "race_started"
    RACE_FINISHED = "race_finished"
    LAP_STARTED = "lap_started"
    LAP_COMPLETED = "lap_completed"

    # Position changes
    POSITION_CHANGED = "position_changed"
    OVERTAKE_ATTEMPTED = "overtake_attempted"
    OVERTAKE_COMPLETED = "overtake_completed"
    OVERTAKE_FAILED = "overtake_failed"

    # Pit stops
    PIT_STOP_STARTED = "pit_stop_started"
    PIT_STOP_COMPLETED = "pit_stop_completed"
    PIT_STOP_ABORTED = "pit_stop_aborted"

    # Tyres
    TYRE_CHANGED = "tyre_changed"
    TYRE_DEGRADED = "tyre_degraded"

    # Incidents
    INCIDENT_OCCURRED = "incident_occurred"
    SPIN = "spin"
    COLLISION = "collision"
    LOCKUP = "lockup"
    OFF_TRACK = "off_track"
    PUNCTURE = "puncture"
    MECHANICAL_FAILURE = "mechanical_failure"
    RETIREMENT = "retirement"

    # Safety car
    SAFETY_CAR_DEPLOYED = "safety_car_deployed"
    SAFETY_CAR_ENDED = "safety_car_ended"
    SAFETY_CAR_RESTARTED = "safety_car_restarted"
    VSC_DEPLOYED = "vsc_deployed"
    VSC_ENDED = "vsc_ended"

    # Weather
    WEATHER_CHANGED = "weather_changed"

    # Strategy
    STRATEGY_CHANGED = "strategy_changed"

    # Penalties
    PENALTY_ISSUED = "penalty_issued"

    # Fastest lap
    FASTEST_LAP = "fastest_lap"

    # Battles
    BATTLE_STARTED = "battle_started"
    BATTLE_UPDATED = "battle_updated"
    BATTLE_ENDED = "battle_ended"
    BATTLE_SIDE_BY_SIDE = "battle_side_by_side"

    # Defense
    DEFENSE_ACTION = "defense_action"

    # DRS Train
    DRS_TRAIN_FORMED = "drs_train_formed"
    DRS_TRAIN_UPDATED = "drs_train_updated"
    DRS_TRAIN_DISSOLVED = "drs_train_dissolved"

    # Phase 7: Environment
    TYRE_CROSSOVER_DETECTED = "tyre_crossover_detected"
    DRYING_LINE_CHANGED = "drying_line_changed"
    RAIN_INTENSITY_CHANGED = "rain_intensity_changed"
    TRACK_WETNESS_CHANGED = "track_wetness_changed"
    OVERTAKE_OPPORTUNITY = "overtake_opportunity"
    FUEL_MODE_CHANGED = "fuel_mode_changed"
    ERS_MODE_CHANGED = "ers_mode_changed"
    TEAM_ORDER_ISSUED = "team_order_issued"
    TEAM_ORDER_EXECUTED = "team_order_executed"

    # Phase 8: sectors
    SECTOR_COMPLETED = "sector_completed"
    SECTOR_OVERTAKE_OPPORTUNITY = "sector_overtake_opportunity"
    SECTOR_OVERTAKE_ATTEMPT = "sector_overtake_attempt"
    SECTOR_INCIDENT = "sector_incident"

    # Phase 8: race procedure
    FORMATION_LAP_STARTED = "formation_lap_started"
    FORMATION_LAP_COMPLETED = "formation_lap_completed"
    START_COMPLETED = "start_completed"
    FIRST_CORNER_COMPLETED = "first_corner_completed"
    RED_FLAG_DEPLOYED = "red_flag_deployed"
    RED_FLAG_LIFTED = "red_flag_lifted"
    STANDING_RESTART = "standing_restart"

    # Phase 8: sessions
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"


class RaceState(str, Enum):
    """Current race state."""

    NOT_STARTED = "not_started"
    GREEN = "green"
    YELLOW = "yellow"
    SAFETY_CAR = "safety_car"
    VSC = "vsc"
    RED_FLAG = "red_flag"
    FINISHED = "finished"


class SimulationEvent(BaseModel):
    """Base simulation event."""

    event_type: EventType
    timestamp: float  # Simulation time in seconds
    lap: int
    driver_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class RaceStartedEvent(SimulationEvent):
    event_type: EventType = EventType.RACE_STARTED
    total_laps: int
    drivers: list[str]


class RaceFinishedEvent(SimulationEvent):
    event_type: EventType = EventType.RACE_FINISHED
    winner_id: str
    results: list[dict[str, Any]]


class LapStartedEvent(SimulationEvent):
    event_type: EventType = EventType.LAP_STARTED
    driver_id: str
    position: int
    tyre_compound: str
    tyre_age: int
    fuel_mass: float


class LapCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.LAP_COMPLETED
    driver_id: str
    position: int
    lap_time: float
    sector_times: list[float]
    tyre_compound: str
    tyre_age: int
    fuel_mass: float
    is_fastest_lap: bool = False


class PositionChangedEvent(SimulationEvent):
    event_type: EventType = EventType.POSITION_CHANGED
    driver_id: str
    old_position: int
    new_position: int
    reason: str  # "overtake", "pit_stop", "incident", "penalty"


class OvertakeAttemptedEvent(SimulationEvent):
    event_type: EventType = EventType.OVERTAKE_ATTEMPTED
    attacker_id: str
    defender_id: str
    success_probability: float


class OvertakeCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.OVERTAKE_COMPLETED
    attacker_id: str
    defender_id: str
    was_successful: bool
    gap_before: float
    gap_after: float


class PitStopStartedEvent(SimulationEvent):
    event_type: EventType = EventType.PIT_STOP_STARTED
    driver_id: str
    position: int
    target_compound: str
    strategy_type: str  # "planned", "reactive", "safety_car"


class PitStopCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.PIT_STOP_COMPLETED
    driver_id: str
    position_before: int
    position_after: int
    stationary_time: float
    total_time_loss: float
    new_compound: str
    tyre_age: int = 0


class TyreChangedEvent(SimulationEvent):
    event_type: EventType = EventType.TYRE_CHANGED
    driver_id: str
    old_compound: str
    new_compound: str
    old_age: int
    reason: str  # "pit_stop", "puncture", "damage"


class IncidentOccurredEvent(SimulationEvent):
    event_type: EventType = EventType.INCIDENT_OCCURRED
    driver_id: str
    incident_type: str  # "spin", "collision", "lockup", "off_track", "puncture", "mechanical"
    severity: float  # 0-1
    time_loss: float
    position_lost: int
    is_retirement: bool = False


class SafetyCarDeployedEvent(SimulationEvent):
    event_type: EventType = EventType.SAFETY_CAR_DEPLOYED
    reason: str
    leader_gap_before: float


class SafetyCarEndedEvent(SimulationEvent):
    event_type: EventType = EventType.SAFETY_CAR_ENDED
    laps_under_safety_car: int


class VSCDeployedEvent(SimulationEvent):
    event_type: EventType = EventType.VSC_DEPLOYED
    reason: str


class VSCEndedEvent(SimulationEvent):
    event_type: EventType = EventType.VSC_ENDED


class WeatherChangedEvent(SimulationEvent):
    event_type: EventType = EventType.WEATHER_CHANGED
    old_condition: str
    new_condition: str
    track_wetness: float
    air_temp: float
    track_temp: float


class StrategyChangedEvent(SimulationEvent):
    event_type: EventType = EventType.STRATEGY_CHANGED
    driver_id: str
    old_strategy: dict[str, Any]
    new_strategy: dict[str, Any]
    reason: str


class FastestLapEvent(SimulationEvent):
    event_type: EventType = EventType.FASTEST_LAP
    driver_id: str
    lap_time: float
    lap: int
    is_overall_fastest: bool = True


class PenaltyIssuedEvent(SimulationEvent):
    event_type: EventType = EventType.PENALTY_ISSUED
    driver_id: str
    penalty_type: str  # "time", "drive_through", "stop_go", "grid_drop", "points"
    value: float
    reason: str


class OvertakeFailedEvent(SimulationEvent):
    event_type: EventType = EventType.OVERTAKE_FAILED
    attacker_id: str
    defender_id: str
    reason: str  # "defended", "incident", "off_track"
    gap_before: float


class BattleStartedEvent(SimulationEvent):
    event_type: EventType = EventType.BATTLE_STARTED
    attacker_id: str
    defender_id: str
    gap: float
    drs_available: bool


class BattleUpdatedEvent(SimulationEvent):
    event_type: EventType = EventType.BATTLE_UPDATED
    attacker_id: str
    defender_id: str
    state: str  # BattleStateType value
    gap: float
    overtake_probability: float


class BattleEndedEvent(SimulationEvent):
    event_type: EventType = EventType.BATTLE_ENDED
    attacker_id: str
    defender_id: str
    reason: str  # "overtake", "gap_increased", "pit_stop", "incident"
    duration_laps: int


class BattleSideBySideEvent(SimulationEvent):
    event_type: EventType = EventType.BATTLE_SIDE_BY_SIDE
    attacker_id: str
    defender_id: str
    gap: float


class DefenseActionEvent(SimulationEvent):
    event_type: EventType = EventType.DEFENSE_ACTION
    defender_id: str
    attacker_id: str
    mode: str  # DefenseMode value
    line_choice: str
    pace_cost: float
    incident_risk_multiplier: float


class DRS_TRAIN_FormedEvent(SimulationEvent):
    event_type: EventType = EventType.DRS_TRAIN_FORMED
    leader_id: str
    members: list[str]
    train_length: int
    gaps: list[float]


class DRS_TRAIN_UpdatedEvent(SimulationEvent):
    event_type: EventType = EventType.DRS_TRAIN_UPDATED
    leader_id: str
    members: list[str]
    train_length: int
    gaps: list[float]


class DRS_TRAIN_DissolvedEvent(SimulationEvent):
    event_type: EventType = EventType.DRS_TRAIN_DISSOLVED
    leader_id: str
    reason: str  # "overtake", "gap_increased", "pit_stop"


class SafetyCarRestartedEvent(SimulationEvent):
    event_type: EventType = EventType.SAFETY_CAR_RESTARTED
    leader_id: str
    field_compressed: bool
    gaps_before: list[float]
    gaps_after: list[float]


class TyreCrossoverEvent(SimulationEvent):
    event_type: EventType = EventType.TYRE_CROSSOVER_DETECTED
    driver_id: str
    old_compound: str
    new_compound: str
    reason: str
    confidence: float
    expected_delta: float


class DryingLineEvent(SimulationEvent):
    event_type: EventType = EventType.DRYING_LINE_CHANGED
    sector: int
    racing_line_wetness: float
    off_line_wetness: float
    drying_rate: float


class OvertakeOpportunityEvent(SimulationEvent):
    event_type: EventType = EventType.OVERTAKE_OPPORTUNITY
    attacker_id: str
    defender_id: str
    probability: float
    sector: int = 0
    drs_available: bool = False


class RainIntensityChangedEvent(SimulationEvent):
    event_type: EventType = EventType.RAIN_INTENSITY_CHANGED
    old_intensity: float
    new_intensity: float
    precipitation_rate: float


class TrackWetnessChangedEvent(SimulationEvent):
    event_type: EventType = EventType.TRACK_WETNESS_CHANGED
    sector: int = -1  # -1 = global
    old_wetness: float = 0.0
    new_wetness: float = 0.0
    racing_line_wetness: float = 0.0
    off_line_wetness: float = 0.0


class FuelModeChangedEvent(SimulationEvent):
    event_type: EventType = EventType.FUEL_MODE_CHANGED
    driver_id: str
    old_mode: str
    new_mode: str
    reason: str = ""


class ErsModeChangedEvent(SimulationEvent):
    event_type: EventType = EventType.ERS_MODE_CHANGED
    driver_id: str
    old_mode: str
    new_mode: str
    reason: str = ""


class TeamOrderIssuedEvent(SimulationEvent):
    event_type: EventType = EventType.TEAM_ORDER_ISSUED
    team_id: str
    driver_id: str
    order: str  # HOLD_POSITION, LET_TEAMMATE_BY, NO_ATTACK, ATTACK, PIT_PRIORITY, STRATEGIC_SPLIT
    target_driver_id: str | None = None
    reason: str = ""


class TeamOrderExecutedEvent(SimulationEvent):
    event_type: EventType = EventType.TEAM_ORDER_EXECUTED
    team_id: str
    driver_id: str
    order: str
    complied: bool = True


class SectorCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.SECTOR_COMPLETED
    driver_id: str
    sector: int
    sector_time: float
    gap_after_sector: float = 0.0


class SectorOvertakeOpportunityEvent(SimulationEvent):
    event_type: EventType = EventType.SECTOR_OVERTAKE_OPPORTUNITY
    attacker_id: str
    defender_id: str
    sector: int
    probability: float


class SectorOvertakeAttemptEvent(SimulationEvent):
    event_type: EventType = EventType.SECTOR_OVERTAKE_ATTEMPT
    attacker_id: str
    defender_id: str
    sector: int
    success_probability: float


class SectorIncidentEvent(SimulationEvent):
    event_type: EventType = EventType.SECTOR_INCIDENT
    driver_id: str
    sector: int
    incident_type: str
    time_loss: float = 0.0


class FormationLapStartedEvent(SimulationEvent):
    event_type: EventType = EventType.FORMATION_LAP_STARTED
    drivers: list[str] = Field(default_factory=list)


class FormationLapCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.FORMATION_LAP_COMPLETED
    ready_drivers: list[str] = Field(default_factory=list)
    failed_drivers: list[str] = Field(default_factory=list)


class StartCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.START_COMPLETED
    driver_id: str
    reaction_time: float
    launch_quality: float
    position_delta: int


class FirstCornerCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.FIRST_CORNER_COMPLETED
    driver_id: str
    outcome: str
    time_loss: float = 0.0
    positions_lost: int = 0


class RedFlagDeployedEvent(SimulationEvent):
    event_type: EventType = EventType.RED_FLAG_DEPLOYED
    reason: str
    laps_remaining: int = 0


class RedFlagLiftedEvent(SimulationEvent):
    event_type: EventType = EventType.RED_FLAG_LIFTED
    laps_suspended: int = 0


class StandingRestartEvent(SimulationEvent):
    event_type: EventType = EventType.STANDING_RESTART
    leader_id: str
    field_compressed: bool = True


class SessionStartedEvent(SimulationEvent):
    event_type: EventType = EventType.SESSION_STARTED
    session_type: str
    drivers: list[str] = Field(default_factory=list)


class SessionCompletedEvent(SimulationEvent):
    event_type: EventType = EventType.SESSION_COMPLETED
    session_type: str
    winner_id: str | None = None


# Event factory functions
def create_race_started_event(timestamp: float, total_laps: int, drivers: list[str]) -> RaceStartedEvent:  # noqa: E501
    return RaceStartedEvent(
        timestamp=timestamp,
        lap=0,
        total_laps=total_laps,
        drivers=drivers,
    )


def create_lap_completed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    position: int,
    lap_time: float,
    sector_times: list[float],
    tyre_compound: str,
    tyre_age: int,
    fuel_mass: float,
    is_fastest_lap: bool = False,
) -> LapCompletedEvent:
    return LapCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        position=position,
        lap_time=lap_time,
        sector_times=sector_times,
        tyre_compound=tyre_compound,
        tyre_age=tyre_age,
        fuel_mass=fuel_mass,
        is_fastest_lap=is_fastest_lap,
    )


def create_overtake_completed_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    was_successful: bool,
    gap_before: float,
    gap_after: float,
) -> OvertakeCompletedEvent:
    return OvertakeCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        was_successful=was_successful,
        gap_before=gap_before,
        gap_after=gap_after,
    )


def create_pit_stop_completed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    position_before: int,
    position_after: int,
    stationary_time: float,
    total_time_loss: float,
    new_compound: str,
    tyre_age: int = 0,
) -> PitStopCompletedEvent:
    return PitStopCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        position_before=position_before,
        position_after=position_after,
        stationary_time=stationary_time,
        total_time_loss=total_time_loss,
        new_compound=new_compound,
        tyre_age=tyre_age,
    )


def create_incident_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    incident_type: str,
    severity: float,
    time_loss: float,
    position_lost: int,
    is_retirement: bool = False,
) -> IncidentOccurredEvent:
    return IncidentOccurredEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        incident_type=incident_type,
        severity=severity,
        time_loss=time_loss,
        position_lost=position_lost,
        is_retirement=is_retirement,
    )


def create_safety_car_deployed_event(
    timestamp: float,
    lap: int,
    reason: str,
    leader_gap_before: float,
) -> SafetyCarDeployedEvent:
    return SafetyCarDeployedEvent(
        timestamp=timestamp,
        lap=lap,
        reason=reason,
        leader_gap_before=leader_gap_before,
    )


def create_overtake_failed_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    reason: str,
    gap_before: float,
) -> OvertakeFailedEvent:
    return OvertakeFailedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        reason=reason,
        gap_before=gap_before,
    )


def create_battle_started_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    gap: float,
    drs_available: bool,
) -> BattleStartedEvent:
    return BattleStartedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        gap=gap,
        drs_available=drs_available,
    )


def create_battle_updated_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    state: str,
    gap: float,
    overtake_probability: float,
) -> BattleUpdatedEvent:
    return BattleUpdatedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        state=state,
        gap=gap,
        overtake_probability=overtake_probability,
    )


def create_battle_ended_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    reason: str,
    duration_laps: int,
) -> BattleEndedEvent:
    return BattleEndedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        reason=reason,
        duration_laps=duration_laps,
    )


def create_battle_side_by_side_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    gap: float,
) -> BattleSideBySideEvent:
    return BattleSideBySideEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        gap=gap,
    )


def create_defense_action_event(
    timestamp: float,
    lap: int,
    defender_id: str,
    attacker_id: str,
    mode: str,
    line_choice: str,
    pace_cost: float,
    incident_risk_multiplier: float,
) -> DefenseActionEvent:
    return DefenseActionEvent(
        timestamp=timestamp,
        lap=lap,
        defender_id=defender_id,
        attacker_id=attacker_id,
        mode=mode,
        line_choice=line_choice,
        pace_cost=pace_cost,
        incident_risk_multiplier=incident_risk_multiplier,
    )


def create_drs_train_formed_event(
    timestamp: float,
    lap: int,
    leader_id: str,
    members: list[str],
    train_length: int,
    gaps: list[float],
) -> DRS_TRAIN_FormedEvent:
    return DRS_TRAIN_FormedEvent(
        timestamp=timestamp,
        lap=lap,
        leader_id=leader_id,
        members=members,
        train_length=train_length,
        gaps=gaps,
    )


def create_drs_train_updated_event(
    timestamp: float,
    lap: int,
    leader_id: str,
    members: list[str],
    train_length: int,
    gaps: list[float],
) -> DRS_TRAIN_UpdatedEvent:
    return DRS_TRAIN_UpdatedEvent(
        timestamp=timestamp,
        lap=lap,
        leader_id=leader_id,
        members=members,
        train_length=train_length,
        gaps=gaps,
    )


def create_drs_train_dissolved_event(
    timestamp: float,
    lap: int,
    leader_id: str,
    reason: str,
) -> DRS_TRAIN_DissolvedEvent:
    return DRS_TRAIN_DissolvedEvent(
        timestamp=timestamp,
        lap=lap,
        leader_id=leader_id,
        reason=reason,
    )


def create_safety_car_restarted_event(
    timestamp: float,
    lap: int,
    leader_id: str,
    field_compressed: bool,
    gaps_before: list[float],
    gaps_after: list[float],
) -> SafetyCarRestartedEvent:
    return SafetyCarRestartedEvent(
        timestamp=timestamp,
        lap=lap,
        leader_id=leader_id,
        field_compressed=field_compressed,
        gaps_before=gaps_before,
        gaps_after=gaps_after,
    )


def create_weather_changed_event(
    timestamp: float,
    lap: int,
    old_condition: str,
    new_condition: str,
    track_wetness: float,
    racing_line_wetness: float = 0.0,
    off_line_wetness: float = 0.0,
    air_temp: float = 25.0,
    track_temp: float = 35.0,
) -> WeatherChangedEvent:
    return WeatherChangedEvent(
        timestamp=timestamp,
        lap=lap,
        old_condition=old_condition,
        new_condition=new_condition,
        track_wetness=track_wetness,
        air_temp=air_temp,
        track_temp=track_temp,
    )


def create_tyre_crossover_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    old_compound: str,
    new_compound: str,
    reason: str,
    confidence: float,
    expected_delta: float,
) -> TyreCrossoverEvent:
    return TyreCrossoverEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        old_compound=old_compound,
        new_compound=new_compound,
        reason=reason,
        confidence=confidence,
        expected_delta=expected_delta,
    )


def create_drying_line_event(
    timestamp: float,
    lap: int,
    sector: int,
    racing_line_wetness: float,
    off_line_wetness: float,
    drying_rate: float,
) -> DryingLineEvent:
    return DryingLineEvent(
        timestamp=timestamp,
        lap=lap,
        sector=sector,
        racing_line_wetness=racing_line_wetness,
        off_line_wetness=off_line_wetness,
        drying_rate=drying_rate,
    )


def create_overtake_attempted_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    success_probability: float,
) -> OvertakeAttemptedEvent:
    return OvertakeAttemptedEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        success_probability=success_probability,
    )


def create_overtake_opportunity_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    probability: float,
    sector: int = 0,
    drs_available: bool = False,
) -> OvertakeOpportunityEvent:
    return OvertakeOpportunityEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        probability=probability,
        sector=sector,
        drs_available=drs_available,
    )


def create_rain_intensity_changed_event(
    timestamp: float,
    lap: int,
    old_intensity: float,
    new_intensity: float,
    precipitation_rate: float,
) -> RainIntensityChangedEvent:
    return RainIntensityChangedEvent(
        timestamp=timestamp,
        lap=lap,
        old_intensity=old_intensity,
        new_intensity=new_intensity,
        precipitation_rate=precipitation_rate,
    )


def create_track_wetness_changed_event(
    timestamp: float,
    lap: int,
    sector: int = -1,
    old_wetness: float = 0.0,
    new_wetness: float = 0.0,
    racing_line_wetness: float = 0.0,
    off_line_wetness: float = 0.0,
) -> TrackWetnessChangedEvent:
    return TrackWetnessChangedEvent(
        timestamp=timestamp,
        lap=lap,
        sector=sector,
        old_wetness=old_wetness,
        new_wetness=new_wetness,
        racing_line_wetness=racing_line_wetness,
        off_line_wetness=off_line_wetness,
    )


def create_fuel_mode_changed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    old_mode: str,
    new_mode: str,
    reason: str = "",
) -> FuelModeChangedEvent:
    return FuelModeChangedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        old_mode=old_mode,
        new_mode=new_mode,
        reason=reason,
    )


def create_ers_mode_changed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    old_mode: str,
    new_mode: str,
    reason: str = "",
) -> ErsModeChangedEvent:
    return ErsModeChangedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        old_mode=old_mode,
        new_mode=new_mode,
        reason=reason,
    )


def create_team_order_issued_event(
    timestamp: float,
    lap: int,
    team_id: str,
    driver_id: str,
    order: str,
    target_driver_id: str | None = None,
    reason: str = "",
) -> TeamOrderIssuedEvent:
    return TeamOrderIssuedEvent(
        timestamp=timestamp,
        lap=lap,
        team_id=team_id,
        driver_id=driver_id,
        order=order,
        target_driver_id=target_driver_id,
        reason=reason,
    )


def create_team_order_executed_event(
    timestamp: float,
    lap: int,
    team_id: str,
    driver_id: str,
    order: str,
    complied: bool = True,
) -> TeamOrderExecutedEvent:
    return TeamOrderExecutedEvent(
        timestamp=timestamp,
        lap=lap,
        team_id=team_id,
        driver_id=driver_id,
        order=order,
        complied=complied,
    )


def create_sector_completed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    sector: int,
    sector_time: float,
    gap_after_sector: float = 0.0,
) -> SectorCompletedEvent:
    return SectorCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        sector=sector,
        sector_time=sector_time,
        gap_after_sector=gap_after_sector,
    )


def create_sector_overtake_opportunity_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    sector: int,
    probability: float,
) -> SectorOvertakeOpportunityEvent:
    return SectorOvertakeOpportunityEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        sector=sector,
        probability=probability,
    )


def create_sector_overtake_attempt_event(
    timestamp: float,
    lap: int,
    attacker_id: str,
    defender_id: str,
    sector: int,
    success_probability: float,
) -> SectorOvertakeAttemptEvent:
    return SectorOvertakeAttemptEvent(
        timestamp=timestamp,
        lap=lap,
        attacker_id=attacker_id,
        defender_id=defender_id,
        sector=sector,
        success_probability=success_probability,
    )


def create_sector_incident_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    sector: int,
    incident_type: str,
    time_loss: float = 0.0,
) -> SectorIncidentEvent:
    return SectorIncidentEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        sector=sector,
        incident_type=incident_type,
        time_loss=time_loss,
    )


def create_formation_lap_started_event(
    timestamp: float,
    lap: int,
    drivers: list[str],
) -> FormationLapStartedEvent:
    return FormationLapStartedEvent(
        timestamp=timestamp,
        lap=lap,
        drivers=drivers,
    )


def create_formation_lap_completed_event(
    timestamp: float,
    lap: int,
    ready_drivers: list[str],
    failed_drivers: list[str],
) -> FormationLapCompletedEvent:
    return FormationLapCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        ready_drivers=ready_drivers,
        failed_drivers=failed_drivers,
    )


def create_start_completed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    reaction_time: float,
    launch_quality: float,
    position_delta: int,
) -> StartCompletedEvent:
    return StartCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        reaction_time=reaction_time,
        launch_quality=launch_quality,
        position_delta=position_delta,
    )


def create_first_corner_completed_event(
    timestamp: float,
    lap: int,
    driver_id: str,
    outcome: str,
    time_loss: float = 0.0,
    positions_lost: int = 0,
) -> FirstCornerCompletedEvent:
    return FirstCornerCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        driver_id=driver_id,
        outcome=outcome,
        time_loss=time_loss,
        positions_lost=positions_lost,
    )


def create_red_flag_deployed_event(
    timestamp: float,
    lap: int,
    reason: str,
    laps_remaining: int = 0,
) -> RedFlagDeployedEvent:
    return RedFlagDeployedEvent(
        timestamp=timestamp,
        lap=lap,
        reason=reason,
        laps_remaining=laps_remaining,
    )


def create_red_flag_lifted_event(
    timestamp: float,
    lap: int,
    laps_suspended: int = 0,
) -> RedFlagLiftedEvent:
    return RedFlagLiftedEvent(
        timestamp=timestamp,
        lap=lap,
        laps_suspended=laps_suspended,
    )


def create_standing_restart_event(
    timestamp: float,
    lap: int,
    leader_id: str,
    field_compressed: bool = True,
) -> StandingRestartEvent:
    return StandingRestartEvent(
        timestamp=timestamp,
        lap=lap,
        leader_id=leader_id,
        field_compressed=field_compressed,
    )


def create_session_started_event(
    timestamp: float,
    lap: int,
    session_type: str,
    drivers: list[str],
) -> SessionStartedEvent:
    return SessionStartedEvent(
        timestamp=timestamp,
        lap=lap,
        session_type=session_type,
        drivers=drivers,
    )


def create_session_completed_event(
    timestamp: float,
    lap: int,
    session_type: str,
    winner_id: str | None = None,
) -> SessionCompletedEvent:
    return SessionCompletedEvent(
        timestamp=timestamp,
        lap=lap,
        session_type=session_type,
        winner_id=winner_id,
    )
