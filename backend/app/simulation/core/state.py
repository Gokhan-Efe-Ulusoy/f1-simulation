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


class WeatherCondition(str, Enum):
    """Weather conditions."""

    DRY = "dry"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    WET = "wet"  # Track wet but not raining
    CHANGING = "changing"


class TyreCompound(str, Enum):
    """Tyre compounds."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class DriverStatus(str, Enum):
    """Driver status during session."""

    ACTIVE = "active"
    IN_PITS = "in_pits"
    RETIRED = "retired"
    DNF = "dnf"
    DSQ = "dsq"
    NOT_STARTED = "not_started"


class EventVerbosity(str, Enum):
    """Event log verbosity (Phase 8: controls event volume/memory)."""

    MINIMAL = "minimal"  # lifecycle + safety/red-flag + retirements only
    STANDARD = "standard"  # Phase 1-7 default event set
    FULL_TELEMETRY = "full_telemetry"  # + per-sector events


class TelemetrySampling(str, Enum):
    """Telemetry sampling level (Phase 8)."""

    OFF = "off"
    SECTOR = "sector"  # per-sector records
    LAP = "lap"  # per-lap records
    FULL = "full"  # per-sector + resource/battle snapshots


@dataclass
class DriverState:
    """Runtime state of a driver during simulation."""

    driver_id: str
    position: int = 1
    lap: int = 0
    total_time: float = 0.0
    last_lap_time: float | None = None
    best_lap_time: float | None = None
    sector_times: list[float] = field(default_factory=list)

    # Tyre state
    tyre_compound: TyreCompound = TyreCompound.MEDIUM
    tyre_age: int = 0
    tyre_wear: float = 0.0  # 0-1
    tyre_temp: float = 90.0  # Celsius

    # Fuel state
    fuel_mass: float = 110.0  # kg
    fuel_burn_rate: float = 1.8  # kg/lap

    # Status
    status: DriverStatus = DriverStatus.ACTIVE
    dnf_reason: str | None = None

    # Pit stop status
    is_in_pits: bool = False
    drs_active: bool = False

    # Damage
    aero_damage: float = 0.0  # 0-1
    engine_damage: float = 0.0  # 0-1

    # DRS/ERS
    drs_available: bool = False
    ers_mode: str = "medium"  # "low", "medium", "high", "overtake"
    ers_charge: float = 1.0  # 0-1

    # Penalties
    pending_penalty: str | None = None
    penalty_time: float = 0.0

    # Gap to car ahead/behind
    gap_ahead: float = 0.0
    gap_behind: float = 0.0

    # Traffic
    in_traffic: bool = False
    traffic_loss: float = 0.0

    # Phase 7: sector / line / resources
    current_sector: int = 0
    racing_line_position: str = "racing_line"  # racing_line | off_line
    fuel_remaining: float = 110.0  # kg, mirrors fuel_mass for strategy layer
    fuel_target: float = 5.0  # kg target at race end
    fuel_mode: str = "standard"  # rich | standard | lean | conserve
    ers_energy: float = 1.0  # 0-1 battery
    ers_target: float = 0.5  # target ERS at race end


@dataclass
class RaceState:
    """Global race state."""

    current_lap: int = 0
    total_laps: int = 0
    race_state: str = "not_started"  # RaceState enum value
    safety_car_laps_remaining: int = 0
    vsc_active: bool = False
    weather_condition: WeatherCondition = WeatherCondition.DRY
    track_wetness: float = 0.0
    air_temperature: float = 25.0
    track_temperature: float = 35.0
    track_evolution: float = 0.0  # 0-1, track gets faster

    # Safety car
    safety_car_deployed: bool = False
    safety_car_lap: int = 0
    leader_gap_at_sc: float = 0.0

    # Timing
    race_start_time: float = 0.0
    current_time: float = 0.0

    # Fastest lap
    fastest_lap_time: float = float('inf')
    fastest_lap_driver: str | None = None
    fastest_lap_number: int = 0

    # Phase 7: environment
    racing_line_wetness: float = 0.0  # 0-1
    off_line_wetness: float = 0.0  # 0-1
    rain_intensity: float = 0.0  # 0-1
    precipitation_rate: float = 0.0  # mm/hr
    forecast_rain_probability: float = 0.0  # team-visible forecast
    forecast_confidence: float = 1.0


class SimulationConfig(BaseModel):
    """Complete simulation configuration."""

    # Identification
    simulation_id: str = "sim_001"
    seed: int | None = None
    model_version: str = "0.1.0"

    # Session
    session_type: SessionType = SessionType.RACE
    track_id: str = "monaco"
    total_laps: int = 78

    # Weather
    initial_weather: WeatherCondition = WeatherCondition.DRY
    weather_variability: float = 0.1  # 0-1

    # Track
    track_length_km: float = 3.337
    number_of_sectors: int = 3
    overtaking_difficulty: float = 0.8  # 0-1
    tyre_degradation_multiplier: float = 1.0

    # Race parameters
    safety_car_probability: float = 0.15
    vsc_probability: float = 0.10
    incident_probability: float = 0.02

    # Pit stops
    pit_lane_time_loss: float = 22.0  # seconds
    pit_stop_base_time: float = 2.5  # seconds
    pit_stop_variance: float = 0.3

    # Fuel
    fuel_per_lap: float = 1.8  # kg
    fuel_effect_per_10kg: float = 0.035  # seconds per 10kg

    # Tyre
    tyre_warmup_laps: dict[TyreCompound, int] = Field(default_factory=lambda: {
        TyreCompound.SOFT: 1,
        TyreCompound.MEDIUM: 2,
        TyreCompound.HARD: 3,
        TyreCompound.INTERMEDIATE: 1,
        TyreCompound.WET: 1,
    })

    # Performance
    base_lap_time: float = 90.0  # seconds
    drs_effect: float = 0.3  # seconds
    ers_effect: float = 0.2  # seconds per lap in overtake mode

    # Scaling factors (for calibration)
    car_performance_scaling: float = 1.0
    driver_performance_scaling: float = 1.0
    tyre_degradation_scaling: float = 1.0
    fuel_effect_scaling: float = 1.0
    weather_effect_scaling: float = 1.0

    # Phase 7: environment (all documented, validated)
    wetness_accumulation_rate: float = Field(default=0.01, ge=0.001, le=0.05)  # per mm/hr per lap
    drying_rate_base: float = Field(default=0.02, ge=0.005, le=0.1)  # wetness per lap
    racing_line_drying_multiplier: float = Field(default=1.5, ge=1.0, le=3.0)  # unitless
    off_line_wetness_multiplier: float = Field(default=1.2, ge=1.0, le=2.0)  # unitless
    rain_transition_threshold: float = Field(default=0.3, ge=0.0, le=1.0)  # wetness 0-1
    intermediate_crossover_threshold: float = Field(default=0.25, ge=0.1, le=0.5)  # wetness 0-1
    slick_crossover_threshold: float = Field(default=0.15, ge=0.05, le=0.3)  # wetness 0-1
    forecast_error_sigma: float = Field(default=0.15, ge=0.05, le=0.5)  # probability units
    sector_dirty_air_base: float = Field(default=0.15, ge=0.0, le=1.0)  # sec/lap
    sector_dirty_air_decay: float = Field(default=1.5, ge=0.5, le=3.0)  # exponent, unitless

    # Phase 7: resources (fuel/ERS battle trade-offs)
    ers_attack_cost: float = Field(default=0.25, ge=0.0, le=1.0)  # ERS energy per attack lap
    ers_harvest_rate: float = Field(default=0.15, ge=0.0, le=1.0)  # ERS energy per harvest lap
    fuel_attack_cost: float = Field(default=0.3, ge=0.0, le=2.0)  # extra kg per attack lap
    defense_fuel_cost: float = Field(default=0.15, ge=0.0, le=1.0)  # extra kg per defend lap
    team_order_probability: float = Field(default=0.3, ge=0.0, le=1.0)  # base probability

    # Phase 8: output control (event volume / telemetry sampling)
    event_verbosity: EventVerbosity = EventVerbosity.STANDARD
    telemetry_sampling: TelemetrySampling = TelemetrySampling.OFF

    # Phase 8: race procedure
    formation_lap_enabled: bool = True
    formation_incident_probability: float = Field(default=0.002, ge=0.0, le=0.1)  # per driver
    red_flag_probability: float = Field(default=0.0, ge=0.0, le=0.2)  # per lap
    red_flag_laps: int = Field(default=3, ge=1, le=10)  # suspension length in laps
    standing_restart_on_red_flag: bool = True

    # Phase 8: battle evaluation scope (O(N*K) instead of O(N^2))
    battle_candidate_gap: float = Field(default=2.0, ge=0.5, le=5.0)  # seconds
    battle_planning_horizon: int = Field(default=3, ge=2, le=5)  # laps

    # Phase 18: race control (default False for backward compat with pre-18 baseline; enable explicitly)
    race_control_enabled: bool = False
    enable_yellow_flags: bool = True
    enable_vsc: bool = True
    enable_safety_car: bool = True
    enable_red_flag: bool = True
    enable_first_lap_incidents: bool = True
    weather_event_coupling: bool = True

    # Phase 19: advanced strategy (default False for backward compat)
    strategy_enabled: bool = False
    strategy_max_candidates: int = Field(default=8, ge=3, le=20)
    strategy_uncertainty_enabled: bool = True
    strategy_opponent_model_enabled: bool = True
    strategy_weather_enabled: bool = True
    strategy_race_control_enabled: bool = True
    strategy_tyre_enabled: bool = True

    # Output
    record_events: bool = True
    record_lap_times: bool = True
    record_telemetry: bool = False

    model_config = {"use_enum_values": True}


class LapTimeComponents(BaseModel):
    """Breakdown of lap time components for analysis."""

    base_time: float
    car_delta: float
    driver_delta: float
    fuel_delta: float
    tyre_delta: float
    tyre_degradation_delta: float
    weather_delta: float
    traffic_delta: float
    track_evolution_delta: float
    drs_delta: float = 0.0
    ers_delta: float = 0.0
    damage_delta: float = 0.0
    stochastic_delta: float = 0.0
    total: float

    model_config = {"use_enum_values": True}


class DriverResult(BaseModel):
    """Final result for a driver."""

    driver_id: str
    position: int
    total_time: float | None = None
    laps_completed: int
    best_lap_time: float | None = None
    best_lap_number: int | None = None
    status: DriverStatus = DriverStatus.ACTIVE
    dnf_reason: str | None = None
    pit_stops: int = 0
    tyre_stints: list[dict[str, Any]] = Field(default_factory=list)
    fastest_lap_rank: int | None = None
    points: float = 0.0

    model_config = {"use_enum_values": True}


class RaceResult(BaseModel):
    """Complete race simulation result."""

    simulation_id: str
    seed: int | None
    model_version: str
    track_id: str
    session_type: SessionType
    total_laps: int
    completed_laps: int
    results: list[DriverResult]
    events: list[dict[str, Any]] = Field(default_factory=list)
    fastest_lap: dict[str, Any] | None = None
    weather_history: list[dict[str, Any]] = Field(default_factory=list)
    safety_car_periods: list[dict[str, Any]] = Field(default_factory=list)
    start_time: str
    end_time: str
    duration_seconds: float

    # Phase 8: telemetry + reproducibility metadata
    telemetry: list[dict[str, Any]] = Field(default_factory=list)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    simulation_version: str = "1.0.0"
    config_version: str = "1.0.0"

    model_config = {"use_enum_values": True}
