from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """High-level strategy type."""

    ONE_STOP = "one_stop"
    TWO_STOP = "two_stop"
    THREE_STOP = "three_stop"
    ZERO_STOP = "zero_stop"  # e.g. Monaco
    FLEXIBLE = "flexible"  # Decide during race


class PitStopType(str, Enum):
    """Type of pit stop."""

    PLANNED = "planned"
    REACTIVE = "reactive"      # Reaction to safety car, incident, etc.
    EMERGENCY = "emergency"    # Puncture, damage
    SPLASH_AND_DASH = "splash_and_dash"  # Minimal fuel/tyre change


class PitStopPhase(str, Enum):
    """Pit stop phase."""

    APPROACHING = "approaching"
    ENTERING = "entering"
    STOPPED = "stopped"
    LEAVING = "leaving"
    REJOINING = "rejoining"
    COMPLETE = "complete"


@dataclass
class PitStopEvent:
    """A single pit stop event."""

    driver_id: str
    lap: int
    stop_type: PitStopType = PitStopType.PLANNED

    # Timing
    pit_entry_time: float = 0.0  # Time crossing pit entry line
    pit_exit_time: float = 0.0   # Time crossing pit exit line
    stationary_time: float = 0.0  # Time stationary in box
    total_time_loss: float = 0.0  # vs staying on track

    # Tyres
    old_compound: str = ""
    new_compound: str = ""
    old_tyre_age: int = 0

    # Fuel (if refueling allowed in future)
    fuel_added: float = 0.0

    # Position
    position_before: int = 0
    position_after: int = 0
    positions_lost: int = 0
    positions_gained: int = 0

    # Issues
    had_issue: bool = False
    issue_type: str | None = None  # "slow_stop", "wheel_nut", "fuel", "penalty"
    issue_time_loss: float = 0.0

    # Strategy
    was_planned: bool = True
    trigger_reason: str = "scheduled"

    model_config = {"use_enum_values": True}


class RaceStrategy(BaseModel):
    """Planned race strategy for a driver."""

    driver_id: str
    strategy_type: StrategyType = StrategyType.TWO_STOP

    # Planned stops
    planned_stops: list[dict[str, Any]] = Field(default_factory=list)
    # Each: {"lap": int, "compound": str, "stint": int, "reason": str}

    # Tyre allocation for the race
    starting_compound: str = "medium"
    available_sets: dict[str, int] = Field(default_factory=dict)

    # Fuel
    starting_fuel_kg: float = 110.0
    target_fuel_per_stint: list[float] = Field(default_factory=list)

    # Flexibility
    pit_window_early: int = 3  # Laps before planned
    pit_window_late: int = 5   # Laps after planned
    reactive_to_safety_car: bool = True
    reactive_to_incidents: bool = True

    # Undercut/Overcut
    undercut_threshold: float = 1.5  # sec/lap advantage needed
    overcut_threshold: float = 1.0   # sec/lap advantage needed

    model_config = {"use_enum_values": True}

    def get_planned_stop_laps(self) -> list[int]:
        return [stop["lap"] for stop in self.planned_stops]

    def get_next_stop(self, current_lap: int) -> dict | None:
        for stop in self.planned_stops:
            if stop["lap"] > current_lap:
                return stop
        return None


# Alias for backwards compatibility
PitStopStrategy = RaceStrategy


class StrategyOption(BaseModel):
    """A complete strategy option for evaluation."""

    strategy_id: str
    strategy_type: StrategyType

    # Stints
    stints: list[dict[str, Any]] = Field(default_factory=list)
    # Each: {"compound": str, "laps": int, "fuel_start": float, "estimated_time": float}

    # Total time
    total_estimated_time: float = 0.0
    total_pit_time_loss: float = 0.0

    # Risk assessment
    risk_score: float = 0.0  # 0-100
    risk_factors: list[str] = Field(default_factory=list)

    # Sensitivity
    sensitivity_to_safety_car: float = 0.0  # -1 to 1, negative = benefits from SC
    sensitivity_to_rain: float = 0.0
    sensitivity_to_degradation: float = 0.0
    sensitivity_to_traffic: float = 0.0

    # Tyre usage
    compounds_used: dict[str, int] = Field(default_factory=dict)
    sets_required: dict[str, int] = Field(default_factory=dict)

    # Feasibility
    is_feasible: bool = True
    feasibility_issues: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class StrategyEvaluation(BaseModel):
    """Evaluation of a strategy option."""

    strategy: StrategyOption
    expected_position: float = 0.0
    position_range: tuple[int, int] = (1, 20)
    win_probability: float = 0.0
    podium_probability: float = 0.0
    points_expectation: float = 0.0

    # Key metrics
    avg_lap_time: float = 0.0
    best_lap_time: float = 0.0
    tyre_life_margin: dict[str, float] = Field(default_factory=dict)
    # compound -> laps remaining at end

    # Scenarios
    scenario_results: dict[str, dict] = Field(default_factory=dict)
    # "safety_car", "rain", "high_deg" -> {position, time_loss}

    model_config = {"use_enum_values": True}


@dataclass
class PitStopState:
    """Runtime state of a pit stop."""

    driver_id: str
    phase: PitStopPhase = PitStopPhase.APPROACHING
    target_compound: str = ""
    target_lap: int = 0

    # Progress
    phase_start_time: float = 0.0
    elapsed_in_phase: float = 0.0

    # Issue simulation
    issue_triggered: bool = False
    issue_type: str | None = None
    issue_delay: float = 0.0

    # Crew performance
    crew_performance_factor: float = 1.0  # 1.0 = nominal

    def reset(self) -> None:
        self.phase = PitStopPhase.APPROACHING
        self.elapsed_in_phase = 0.0
        self.issue_triggered = False
        self.issue_type = None
        self.issue_delay = 0.0


class PitStopModel(BaseModel):
    """Pit stop time model."""

    # Base times
    pit_lane_drive_through_time: float = 22.0  # Entry to exit at speed limit
    stationary_base_time: float = 2.4  # Optimal stop
    stationary_variance: float = 0.15  # Standard deviation

    # Team performance
    team_pit_skill_factor: float = 1.0  # Multiplier on stationary time

    # Issue probabilities (per stop)
    issue_probability: float = 0.02
    issue_types: dict[str, dict[str, Any]] = Field(default_factory=lambda: {
        "slow_stop": {"probability": 0.01, "delay": (1.0, 3.0), "description": "Slow wheel change"},
        "wheel_nut": {"probability": 0.005, "delay": (5.0, 15.0), "description": "Stuck wheel nut"},
        "front_wing": {"probability": 0.003, "delay": (3.0, 8.0), "description": "Front wing change"},  # noqa: E501
        "penalty": {"probability": 0.001, "delay": (5.0, 10.0), "description": "Unsafe release"},
    })

    # Compound change time (some compounds slightly different)
    compound_change_modifier: dict[str, float] = Field(default_factory=lambda: {
        "soft": 1.0,
        "medium": 1.0,
        "hard": 1.0,
        "intermediate": 1.02,  # Slightly heavier
        "wet": 1.02,
    })

    model_config = {"use_enum_values": True}

    def calculate_stop_time(
        self,
        compound: str,
        team_factor: float = 1.0,
        rng: Any = None,
    ) -> tuple[float, dict[str, Any]]:
        """Calculate total pit stop time loss.
        
        Returns (total_time_loss, details_dict)
        """
        if rng is None:
            import numpy as np
            rng = np.random.default_rng()

        # Pit lane drive-through (fixed based on track)
        pit_lane_time = self.pit_lane_drive_through_time

        # Stationary time
        base_stationary = self.stationary_base_time * self.compound_change_modifier.get(compound, 1.0)  # noqa: E501
        stationary = rng.normal(base_stationary * team_factor, self.stationary_variance * team_factor)  # noqa: E501
        stationary = max(1.8, stationary)  # Minimum realistic

        # Check for issues
        issue = None
        issue_delay = 0.0
        roll = rng.random()
        cumulative = 0.0

        for issue_name, issue_data in self.issue_types.items():
            cumulative += issue_data["probability"] * self.issue_probability / 0.02
            if roll < cumulative:
                issue = issue_name
                delay_range = issue_data["delay"]
                issue_delay = rng.uniform(delay_range[0], delay_range[1])
                break

        total = pit_lane_time + stationary + issue_delay

        return total, {
            "pit_lane_time": pit_lane_time,
            "stationary_time": stationary,
            "issue": issue,
            "issue_delay": issue_delay,
            "total_time_loss": total,
        }

    def calculate_stationary_time(
        self,
        compound: str,
        team_factor: float = 1.0,
        rng: Any = None,
    ) -> float:
        """Calculate just the stationary time."""
        if rng is None:
            import numpy as np
            rng = np.random.default_rng()

        base = self.stationary_base_time * self.compound_change_modifier.get(compound, 1.0)
        return max(1.8, rng.normal(base * team_factor, self.stationary_variance * team_factor))


# Standard pit stop model
DEFAULT_PIT_STOP_MODEL = PitStopModel()


def estimate_pit_stop_loss(
    track_pit_lane_time: float,
    compound: str,
    team_pit_skill: float,
    rng: Any = None,
) -> float:
    """Quick estimate of pit stop time loss.
    
    track_pit_lane_time: Track-specific pit lane time loss
    compound: Tyre compound
    team_pit_skill: 0-100, higher = better
    """
    if rng is None:
        import numpy as np
        rng = np.random.default_rng()

    # Team factor: 100 = 0.95x, 50 = 1.0x, 0 = 1.1x
    team_factor = 1.1 - (team_pit_skill / 100) * 0.15

    stationary = rng.normal(2.4 * team_factor, 0.15 * team_factor)
    stationary = max(1.8, stationary)

    compound_mod = {"soft": 1.0, "medium": 1.0, "hard": 1.0, "intermediate": 1.02, "wet": 1.02}
    stationary *= compound_mod.get(compound, 1.0)

    # Small chance of issue
    if rng.random() < 0.02:
        stationary += rng.uniform(1.0, 5.0)

    return track_pit_lane_time + stationary
