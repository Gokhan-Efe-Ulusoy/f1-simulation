from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionType(str, Enum):
    """Types of F1 sessions."""

    PRACTICE_1 = "practice_1"
    PRACTICE_2 = "practice_2"
    PRACTICE_3 = "practice_3"
    QUALIFYING = "qualifying"
    SPRINT_QUALIFYING = "sprint_qualifying"
    SPRINT = "sprint"
    RACE = "race"


class SessionFormat(str, Enum):
    """Weekend format."""

    STANDARD = "standard"      # FP1, FP2, FP3, Quali, Race
    SPRINT = "sprint"          # FP1, Sprint Quali, Sprint, Quali, Race
    SPRINT_SHOOTOUT = "sprint_shootout"  # FP1, Sprint Shootout, Sprint, Quali, Race


class QualifyingFormat(str, Enum):
    """Qualifying format."""

    KNOCKOUT = "knockout"      # Q1, Q2, Q3
    SINGLE = "single"          # Single session
    SPRINT = "sprint"          # Sprint qualifying (shorter)


@dataclass
class DriverSessionState:
    """Driver state within a session."""

    driver_id: str

    # Timing
    laps_completed: int = 0
    total_time: float = 0.0
    best_lap_time: float | None = None
    best_sector_times: list[float] = field(default_factory=lambda: [float('inf'), float('inf'), float('inf')])  # noqa: E501
    current_lap_time: float = 0.0
    current_sector: int = 0
    sector_times: list[float] = field(default_factory=list)

    # Position
    position: int = 1
    gap_to_leader: float = 0.0
    gap_ahead: float = 0.0
    gap_behind: float = 0.0

    # Tyres
    compound: str = "medium"
    tyre_age: int = 0
    tyre_wear: float = 0.0
    tyre_set_id: str | None = None

    # Fuel
    fuel_mass: float = 0.0
    fuel_start_lap: float = 0.0

    # Status
    is_in_pits: bool = False
    is_on_track: bool = True
    has_set_time: bool = False
    is_flying_lap: bool = False
    is_out_lap: bool = False
    is_in_lap: bool = False

    # Quali specific
    quali_segment: str | None = None  # Q1, Q2, Q3
    eliminated: bool = False

    # Penalties
    grid_penalty: int = 0
    time_penalty: float = 0.0

    # Incidents
    incident_count: int = 0
    last_incident_lap: int = -1


@dataclass
class SessionState:
    """Overall session state."""

    session_type: SessionType
    track_id: str
    total_time_seconds: float = 0.0  # For practice/quali
    total_laps: int = 0  # For race
    current_lap: int = 0
    elapsed_time: float = 0.0
    remaining_time: float = 0.0

    # Weather
    weather: Any = None

    # Track state
    track_evolution: float = 0.0
    rubber_level: float = 0.0

    # Session control
    is_active: bool = False
    is_finished: bool = False
    red_flag: bool = False
    safety_car: bool = False
    vsc: bool = False

    # Driver states
    drivers: dict[str, DriverSessionState] = field(default_factory=dict)

    # Timing
    sector_times: dict[str, list[float]] = field(default_factory=dict)  # driver_id -> [s1, s2, s3]
    lap_times: dict[str, list[float]] = field(default_factory=dict)  # driver_id -> [lap_times]

    # Events
    events: list[dict] = field(default_factory=list)

    def get_classification(self) -> list[tuple[str, float]]:
        """Get current classification (driver_id, sort_key)."""
        results = []
        for driver_id, state in self.drivers.items():
            if state.eliminated:
                sort_key = (1, -state.laps_completed, state.best_lap_time or float('inf'))
            elif state.is_on_track:
                sort_key = (0, -state.laps_completed, state.total_time)
            else:
                sort_key = (0, -state.laps_completed, state.total_time)
            results.append((driver_id, sort_key))

        results.sort(key=lambda x: x[1])
        return [(d, s) for d, s in results]


class SessionConfig(BaseModel):
    """Configuration for a session."""

    session_type: SessionType
    track_id: str

    # Duration
    duration_minutes: float | None = None  # For practice/quali
    total_laps: int | None = None  # For race

    # Format
    format: SessionFormat = SessionFormat.STANDARD
    quali_format: QualifyingFormat = QualifyingFormat.KNOCKOUT

    # Qualifying specific
    q1_duration: float = 18.0  # minutes
    q2_duration: float = 15.0
    q3_duration: float = 12.0
    q1_eliminate: int = 5
    q2_eliminate: int = 5

    # Sprint specific
    sprint_laps: int | None = None
    sprint_points: list[int] = Field(default_factory=lambda: [8, 7, 6, 5, 4, 3, 2, 1])

    # Weather
    weather_condition: str = "dry"
    weather_volatility: float = 0.1

    # Track
    track_evolution_start: float = 0.0

    # Parc ferme
    parc_ferme: bool = True

    # Tire allocation (per driver)
    tyre_allocation: dict[str, int] = Field(default_factory=lambda: {
        "soft": 8,
        "medium": 3,
        "hard": 2,
        "intermediate": 4,
        "wet": 3,
    })

    # Fuel
    max_fuel_kg: float = 110.0

    model_config = {"use_enum_values": True}


class SessionResult(BaseModel):
    """Result of a session."""

    session_type: SessionType
    track_id: str
    session_config: SessionConfig

    # Classification
    classification: list[dict[str, Any]] = Field(default_factory=list)
    # Each entry: driver_id, position, laps, best_time, gap, status, tyre_compound, etc.

    # Timing
    fastest_lap: dict[str, Any] | None = None  # driver_id, time, lap
    fastest_sectors: dict[int, dict[str, Any]] = Field(default_factory=dict)  # sector -> driver_id, time  # noqa: E501

    # Weather
    weather_summary: dict[str, Any] = Field(default_factory=dict)

    # Events
    events: list[dict] = Field(default_factory=list)

    # Penalties
    penalties: list[dict[str, Any]] = Field(default_factory=list)

    # Metadata
    start_time: str
    end_time: str
    duration_seconds: float

    model_config = {"use_enum_values": True}


class RaceConfig(SessionConfig):
    """Race-specific configuration."""

    session_type: SessionType = SessionType.RACE
    total_laps: int

    # Pit stops
    min_pit_stops: int = 1
    max_pit_stops: int = 3
    pit_window_start: int = 5  # Lap
    pit_window_end: int = -5  # Relative to end

    # Safety car
    safety_car_probability: float = 0.15
    vsc_probability: float = 0.10

    # Incidents
    incident_probability: float = 0.02

    # Points
    points_system: list[int] = Field(default_factory=lambda: [25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
    fastest_lap_point: bool = True

    # DRS
    drs_activation_lap: int = 2
    drs_zones: int = 2

    model_config = {"use_enum_values": True}


class RaceResult(SessionResult):
    """Race-specific result."""

    session_type: SessionType = SessionType.RACE

    # Race specific
    winner_id: str
    podium: list[str] = Field(default_factory=list)  # [1st, 2nd, 3rd]
    dnfs: list[dict[str, Any]] = Field(default_factory=list)

    # Strategy
    pit_stop_summary: dict[str, list[dict]] = Field(default_factory=dict)
    # driver_id -> [{lap, compound, stint_length, position_lost}, ...]

    # Safety car
    safety_car_periods: list[dict[str, Any]] = Field(default_factory=list)
    vsc_periods: list[dict[str, Any]] = Field(default_factory=list)

    # Overtakes
    overtakes: list[dict[str, Any]] = Field(default_factory=list)
    # {attacker, defender, lap, success}

    model_config = {"use_enum_values": True}
