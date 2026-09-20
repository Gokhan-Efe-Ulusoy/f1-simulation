from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.simulation.environment.models import (
    ForecastUncertainty,
    OvertakeZone,
)


class OvertakePhase(str, Enum):
    """Phase of an overtake attempt."""
    NO_OPPORTUNITY = "no_opportunity"
    CLOSING = "closing"
    WITHIN_ATTACK_RANGE = "within_attack_range"
    OVERTAKE_OPPORTUNITY = "overtake_opportunity"
    OVERTAKE_ATTEMPT = "overtake_attempt"
    DEFENSE = "defense"
    SUCCESS = "success"
    FAILURE = "failure"
    INCIDENT = "incident"


class BattleStateType(str, Enum):
    """State of a battle between two drivers."""
    NO_BATTLE = "no_battle"
    CLOSING = "closing"
    WITHIN_DRS = "within_drs"
    ATTACKING = "attacking"
    DEFENDING = "defending"
    SIDE_BY_SIDE = "side_by_side"
    OVERTAKE_COMPLETED = "overtake_completed"
    BATTLE_ENDED = "battle_ended"


class DefenseMode(str, Enum):
    """Defensive driving mode."""
    NORMAL = "normal"
    DEFENSIVE = "defensive"
    AGGRESSIVE = "aggressive"


class SafetyCarPhase(str, Enum):
    """Safety car phase."""
    NOT_DEPLOYED = "not_deployed"
    DEPLOYED = "deployed"
    RESTART_PREPARATION = "restart_preparation"
    RESTART = "restart"
    POST_RESTART = "post_restart"


@dataclass
class OvertakeDecision:
    """Result of overtake evaluation."""
    opportunity_exists: bool
    phase: OvertakePhase
    probability: float  # 0-1
    factors: dict[str, float]  # Contributing factors
    recommended_action: str  # "attack", "wait", "back_off"
    debug_info: dict[str, Any]


@dataclass
class BattleState:
    """Persistent battle state between two drivers."""
    attacker_id: str
    defender_id: str
    state: BattleStateType = BattleStateType.NO_BATTLE
    laps_active: int = 0
    gap: float = 0.0
    min_gap: float = float('inf')
    max_gap: float = 0.0
    side_by_side_laps: int = 0
    attack_attempts: int = 0
    successful_overtakes: int = 0
    incidents: int = 0
    drs_available_laps: int = 0
    created_lap: int = 0
    last_update_lap: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BattleDecision:
    """Result of battle evaluation."""
    new_state: BattleStateType
    overtake_probability: float
    defense_mode: DefenseMode
    incident_risk_multiplier: float
    debug_info: dict[str, Any]


@dataclass
class DirtyAirContext:
    """Context for dirty air calculation."""
    following_distance: float  # seconds
    corner_type: str
    follower_aero_sensitivity: float  # 0-100
    leader_aero_efficiency: float  # 0-100
    weather: str
    track_wetness: float
    speed_kmh: float
    sector_dirty_air_sensitivity: float | None = None
    sector: int = 0


@dataclass
class DirtyAirEffect:
    """Result of dirty air calculation."""
    cornering_loss: float  # sec/lap
    braking_loss: float  # sec/lap
    tyre_temp_increase: float  # Celsius
    degradation_multiplier: float  # multiplier on base degradation
    total_pace_loss: float  # sec/lap


@dataclass
class DRSTrainContext:
    """Context for DRS train detection."""
    positions: list[dict[str, Any]]  # [{"driver_id": ..., "position": ..., "gap_ahead": ...}, ...]
    track_drs_zones: int
    drs_detection_gap: float = 1.0  # seconds


@dataclass
class DRSTrainInfo:
    """DRS train information."""
    train_detected: bool
    leader_id: str | None
    members: list[str]
    train_length: int
    gaps: list[float]
    effective_overtake_opportunity: bool
    debug_info: dict[str, Any]


@dataclass
class DefenseDecision:
    """Result of defense evaluation."""
    mode: DefenseMode
    line_choice: str  # "inside", "outside", "middle", "variable"
    incident_risk_multiplier: float
    pace_cost: float  # sec/lap cost of defending
    debug_info: dict[str, Any]


@dataclass
class SafetyCarRestartContext:
    """Context for safety car restart."""
    driver_id: str
    position: int
    gap_to_ahead: float
    tyre_compound: str
    tyre_age: int
    tyre_temp: float
    start_performance: float  # 0-100
    pressure_resistance: float
    aggression: float
    consistency: float
    weather: str
    track_wetness: float
    track_temp: float
    laps_under_sc: int
    is_leader: bool


@dataclass
class SafetyCarRestartResult:
    """Result of safety car restart evaluation."""
    reaction_time: float  # seconds
    acceleration_advantage: float  # relative to average
    position_change_probability: dict[int, float]  # position delta -> prob
    incident_risk: float
    debug_info: dict[str, Any]


@dataclass
class BattleResourceState:
    """Resource state affecting battle decisions (fuel, ERS, tyres)."""
    fuel_mass: float  # kg
    fuel_target: float  # target fuel at end of stint
    fuel_mode: str  # "rich", "standard", "lean", "conserve"
    ers_energy: float  # 0-1 (ERS battery state)
    ers_mode: str  # "overtake", "high", "medium", "low", "conserve"
    ers_target: float  # target ERS at end of stint
    tyre_condition: float  # 0-1 (1 = fresh)
    tyre_wear: float  # 0-1
    tyre_compound: str
    tyre_age: int

    # Resource management
    fuel_delta_to_target: float = 0.0  # positive = over target
    ers_delta_to_target: float = 0.0
    can_attack: bool = True  # Whether resources allow attacking
    fuel_conservation_required: bool = False
    ers_conservation_required: bool = False


@dataclass
class BattleContext:
    """Context for battle evaluation."""
    attacker_id: str
    defender_id: str
    gap: float
    relative_pace: float
    tyre_delta: float
    drs_state: bool
    attacker_ers_mode: str
    defender_ers_mode: str
    track_overtaking_difficulty: float
    dirty_air: float
    attacker_overtaking_skill: float
    defender_defensive_skill: float
    attacker_aggression: float
    defender_aggression: float
    attacker_tyre_condition: float  # 0-1
    defender_tyre_condition: float  # 0-1
    weather: str
    track_wetness: float
    attacker_damage: float
    defender_damage: float
    safety_car_active: bool
    vsc_active: bool
    current_lap: int
    race_laps_remaining: int

    # Phase 7 additions
    attacker_resource_state: BattleResourceState | None = None
    defender_resource_state: BattleResourceState | None = None
    overtake_zone: OvertakeZone | None = None
    sector: int = 0
    forecast: ForecastUncertainty | None = None
    track_wetness_racing_line: float = 0.0
    track_wetness_off_line: float = 0.0
    drying_line_active: bool = False


@dataclass
class OvertakeContext:
    """Context for overtake evaluation."""
    attacker_id: str
    defender_id: str
    attacker_position: int
    defender_position: int
    gap: float  # seconds
    relative_pace: float  # attacker pace - defender pace (sec/lap, negative = attacker faster)
    attacker_tyre_compound: str
    defender_tyre_compound: str
    attacker_tyre_age: int
    defender_tyre_age: int
    tyre_delta: float  # pace advantage from tyre difference (sec/lap, positive = attacker advantage)  # noqa: E501
    attacker_ers_mode: str
    defender_ers_mode: str
    drs_available: bool
    attacker_straight_line_advantage: float  # sec/lap
    defender_defensive_skill: float  # 0-100
    attacker_overtaking_skill: float  # 0-100
    attacker_aggression: float  # 0-100
    track_overtaking_difficulty: float  # 0-1 normalized
    corner_type: str
    dirty_air_effect: float  # performance loss from dirty air (sec/lap)
    weather: str
    track_wetness: float
    attacker_damage: float  # 0-1
    defender_damage: float  # 0-1
    safety_car_active: bool
    vsc_active: bool
    traffic_ahead: bool

    # Phase 7 additions
    attacker_resource_state: BattleResourceState | None = None
    defender_resource_state: BattleResourceState | None = None
    overtake_zone: OvertakeZone | None = None
    sector: int = 0
    forecast: ForecastUncertainty | None = None
    track_wetness_racing_line: float = 0.0
    track_wetness_off_line: float = 0.0
    drying_line_active: bool = False
    attacker_ers_energy: float = 1.0
    defender_ers_energy: float = 1.0


@dataclass
class DefenseContext:
    """Context for defense decision."""
    defender_id: str
    attacker_id: str
    gap: float
    relative_pace: float
    defender_defensive_skill: float
    defender_aggression: float
    defender_pressure_resistance: float
    defender_tyre_condition: float
    attacker_overtaking_skill: float
    attacker_aggression: float
    attacker_tyre_condition: float
    track_overtaking_difficulty: float
    corner_type: str
    weather: str
    track_wetness: float
    laps_remaining: int
    position: int

    # Phase 7 additions
    defender_resource_state: BattleResourceState | None = None
    attacker_resource_state: BattleResourceState | None = None
    overtake_zone: OvertakeZone | None = None
    sector: int = 0
    forecast: ForecastUncertainty | None = None
    track_wetness_racing_line: float = 0.0
    track_wetness_off_line: float = 0.0
    drying_line_active: bool = False
    is_teammate: bool = False
    team_order: str | None = None  # "hold", "let_by", "attack", "pit_priority"


class OvertakeConfig(BaseModel):
    """Configuration for overtake model."""
    # Base coefficients
    base_opportunity_gap: float = 1.2  # Max gap for any opportunity (seconds)
    attack_range_gap: float = 0.8  # Gap for active attack (seconds)
    drs_gap_threshold: float = 1.0  # DRS activation gap (seconds)

    # Pace factors
    pace_advantage_coeff: float = 1.5  # per sec/lap advantage
    tyre_delta_coeff: float = 2.0  # per sec/lap tyre advantage
    straight_line_coeff: float = 1.0  # per sec/lap straight advantage

    # Skill factors
    overtaking_skill_coeff: float = 0.015  # per skill point
    defending_skill_coeff: float = -0.012  # per skill point
    aggression_coeff: float = 0.008  # per aggression point

    # Track factors
    track_difficulty_coeff: float = -1.5  # per 0-1 difficulty
    corner_type_modifiers: dict[str, float] = Field(default_factory=lambda: {
        "hairpin": 0.3,
        "slow": 0.2,
        "medium": 0.1,
        "fast": -0.1,
        "high_speed": -0.2,
        "chicane": 0.15,
        "double_apex": 0.05,
    })

    # DRS
    drs_enabled_bonus: float = 0.25  # base probability bonus
    drs_effectiveness_coeff: float = 1.0  # multiplier on DRS effect

    # ERS
    ers_overtake_bonus: float = 0.15
    ers_high_bonus: float = 0.08

    # Conditions
    wet_penalty: float = -0.4
    damp_penalty: float = -0.2
    damage_penalty: float = -0.5  # per 0-1 damage

    # Traffic
    traffic_penalty: float = -0.15

    # Base probability scaling
    base_probability: float = 0.1
    max_probability: float = 0.85

    model_config = {"use_enum_values": True}


class BattleConfig(BaseModel):
    """Configuration for battle model."""
    # Battle creation
    battle_creation_gap: float = 1.5  # seconds
    battle_drs_gap: float = 1.0  # seconds

    # Battle persistence
    battle_termination_gap: float = 3.0  # seconds
    max_battle_laps: int = 10

    # State transitions
    closing_to_attacking_gap: float = 0.9
    attacking_to_side_by_side_gap: float = 0.2
    side_by_side_timeout_laps: int = 3

    # Side-by-side
    side_by_side_overtake_bonus: float = 0.3
    side_by_side_incident_multiplier: float = 2.5

    # DRS
    drs_effectiveness_in_battle: float = 1.0

    # Defense thresholds (from DefenseConfig)
    normal_defense_threshold: float = 0.5
    defensive_defense_threshold: float = 0.2
    aggressive_defense_threshold: float = -0.1

    model_config = {"use_enum_values": True}


class DirtyAirConfig(BaseModel):
    """Configuration for dirty air model."""
    # Distance decay
    reference_distance: float = 1.0  # seconds
    distance_exponent: float = 1.5

    # Aero sensitivity
    aero_sensitivity_coeff: float = 0.015  # per sensitivity point
    aero_efficiency_coeff: float = 0.01  # per efficiency point

    # Corner type modifiers
    corner_modifiers: dict[str, float] = Field(default_factory=lambda: {
        "hairpin": 1.5,
        "slow": 1.3,
        "medium": 1.0,
        "fast": 0.7,
        "high_speed": 0.5,
        "chicane": 1.2,
        "double_apex": 1.1,
    })

    # Weather
    wet_reduction: float = 0.6  # Less dirty air in wet

    # Base losses (at reference distance, 50 sensitivity, medium corner)
    base_cornering_loss: float = 0.15  # sec/lap
    base_braking_loss: float = 0.05  # sec/lap
    base_tyre_temp_increase: float = 3.0  # Celsius
    base_degradation_multiplier: float = 1.15

    model_config = {"use_enum_values": True}


class DRSTrainConfig(BaseModel):
    """Configuration for DRS train model."""
    max_train_gap: float = 1.0  # seconds
    min_train_length: int = 3
    max_train_length: int = 8
    train_dissolution_gap: float = 1.5

    # Train effects
    train_drs_effectiveness_reduction: float = 0.7
    train_overtake_penalty: float = -0.2

    model_config = {"use_enum_values": True}


class DefenseConfig(BaseModel):
    """Configuration for defense model."""
    # Defense modes
    normal_defense_threshold: float = 0.5  # relative pace
    defensive_defense_threshold: float = 0.2
    aggressive_defense_threshold: float = -0.1

    # Skill factors
    defensive_skill_coeff: float = 0.01  # per skill point
    pressure_resistance_coeff: float = 0.008

    # Pace cost of defending (sec/lap)
    normal_pace_cost: float = 0.0
    defensive_pace_cost: float = 0.15
    aggressive_pace_cost: float = 0.35

    # Incident risk multipliers
    normal_risk: float = 1.0
    defensive_risk: float = 1.3
    aggressive_risk: float = 2.0

    # Tyre condition effect
    worn_tyre_aggressive_threshold: float = 0.7  # wear %

    model_config = {"use_enum_values": True}


class SafetyCarRestartConfig(BaseModel):
    """Configuration for safety car restart model."""
    # Field compression
    target_gap_under_sc: float = 0.5  # seconds
    gap_variance: float = 0.15  # seconds

    # Restart factors
    start_skill_coeff: float = 0.02  # per skill point
    tyre_temp_coeff: float = 0.005  # per degree C
    tyre_age_coeff: float = -0.02  # per lap
    reaction_variance: float = 0.15  # seconds

    # Position change
    max_positions_gained: int = 2
    max_positions_lost: int = 3

    # Incident risk
    base_restart_incident_risk: float = 0.02
    aggression_incident_coeff: float = 0.0003
    wet_incident_multiplier: float = 2.5

    model_config = {"use_enum_values": True}
