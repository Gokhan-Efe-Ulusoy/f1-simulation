from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import numpy as np


class EngineMode(str, Enum):
    """Engine mode for fuel strategy."""
    RICH = "rich"        # Maximum power, high fuel consumption
    STANDARD = "standard"  # Balanced
    LEAN = "lean"        # Fuel saving, reduced power
    OVERTAKE = "overtake"  # Short burst of max power
    HARVEST = "harvest"    # Maximum energy recovery


@dataclass
class EngineModeProfile:
    """Engine mode performance profile."""
    name: EngineMode
    fuel_multiplier: float       # Fuel consumption multiplier
    power_multiplier: float      # Power output multiplier
    pace_delta: float            # Lap time delta vs standard (seconds)
    tyre_deg_multiplier: float   # Tyre degradation multiplier
    ers_deployment: float        # ERS deployment level (0-1)
    ers_harvest: float           # ERS harvest level (0-1)
    max_laps: int | None         # Maximum laps sustainable (None = unlimited)
    description: str


# Default engine mode profiles
DEFAULT_ENGINE_MODES: dict[EngineMode, EngineModeProfile] = {
    EngineMode.RICH: EngineModeProfile(
        name=EngineMode.RICH,
        fuel_multiplier=1.12,
        power_multiplier=1.02,
        pace_delta=-0.35,  # 0.35s faster
        tyre_deg_multiplier=1.08,
        ers_deployment=1.0,
        ers_harvest=0.3,
        max_laps=15,
        description="Maximum power for qualifying/overtaking",
    ),
    EngineMode.STANDARD: EngineModeProfile(
        name=EngineMode.STANDARD,
        fuel_multiplier=1.00,
        power_multiplier=1.00,
        pace_delta=0.0,
        tyre_deg_multiplier=1.00,
        ers_deployment=0.7,
        ers_harvest=0.7,
        max_laps=None,
        description="Balanced race pace",
    ),
    EngineMode.LEAN: EngineModeProfile(
        name=EngineMode.LEAN,
        fuel_multiplier=0.88,
        power_multiplier=0.98,
        pace_delta=0.45,  # 0.45s slower
        tyre_deg_multiplier=0.92,
        ers_deployment=0.4,
        ers_harvest=1.0,
        max_laps=None,
        description="Fuel saving mode",
    ),
    EngineMode.OVERTAKE: EngineModeProfile(
        name=EngineMode.OVERTAKE,
        fuel_multiplier=1.20,
        power_multiplier=1.035,
        pace_delta=-0.55,
        tyre_deg_multiplier=1.15,
        ers_deployment=1.0,
        ers_harvest=0.0,
        max_laps=3,
        description="Maximum attack for overtaking",
    ),
    EngineMode.HARVEST: EngineModeProfile(
        name=EngineMode.HARVEST,
        fuel_multiplier=0.85,
        power_multiplier=0.97,
        pace_delta=0.65,
        tyre_deg_multiplier=0.88,
        ers_deployment=0.1,
        ers_harvest=1.0,
        max_laps=None,
        description="Maximum energy recovery",
    ),
}


@dataclass
class FuelPlan:
    """Fuel plan for a stint."""
    stint_laps: int
    engine_mode: EngineMode
    fuel_start_kg: float
    fuel_end_kg: float
    fuel_consumed_kg: float
    total_time_delta: float  # vs standard mode
    avg_lap_time_delta: float


@dataclass
class RaceFuelStrategy:
    """Complete fuel strategy for a race."""
    starting_fuel_kg: float
    stint_plans: list[FuelPlan]
    total_fuel_consumed: float
    total_time_delta: float  # vs all-standard
    engine_mode_sequence: list[EngineMode]
    safety_margin_kg: float = 2.0


class FuelStrategyOptimizer:
    """Optimizes fuel strategy (engine modes) for a given race."""

    def __init__(
        self,
        engine_modes: dict[EngineMode, EngineModeProfile] | None = None,
        base_fuel_consumption: float = 1.8,  # kg/lap at standard mode
        fuel_tank_capacity: float = 110.0,
        min_fuel_reserve: float = 2.0,
    ):
        self.engine_modes = engine_modes or DEFAULT_ENGINE_MODES
        self.base_fuel_consumption = base_fuel_consumption
        self.fuel_tank_capacity = fuel_tank_capacity
        self.min_fuel_reserve = min_fuel_reserve
        self.rng = np.random.default_rng()

    def optimize_stint_fuel(
        self,
        stint_laps: int,
        starting_fuel: float,
        target_end_fuel: float | None = None,
        allow_rich: bool = True,
        allow_overtake: bool = False,
    ) -> list[FuelPlan]:
        """Find optimal engine mode sequence for a stint."""
        if target_end_fuel is None:
            target_end_fuel = self.min_fuel_reserve

        fuel_available = starting_fuel - target_end_fuel
        max_consumption = fuel_available / stint_laps if stint_laps > 0 else 0

        # Determine viable modes based on fuel budget
        viable_modes = []
        for mode, profile in self.engine_modes.items():
            if not allow_rich and mode == EngineMode.RICH:
                continue
            if not allow_overtake and mode == EngineMode.OVERTAKE:
                continue
            if profile.max_laps and stint_laps > profile.max_laps:
                continue

            consumption = self.base_fuel_consumption * profile.fuel_multiplier
            if consumption <= max_consumption * 1.05:  # 5% tolerance
                viable_modes.append(mode)

        if not viable_modes:
            viable_modes = [EngineMode.LEAN]

        # Generate mode sequences (simplified: constant mode per stint)
        plans = []
        for mode in viable_modes:
            profile = self.engine_modes[mode]
            consumption = self.base_fuel_consumption * profile.fuel_multiplier
            fuel_consumed = consumption * stint_laps
            fuel_end = starting_fuel - fuel_consumed

            if fuel_end < self.min_fuel_reserve:
                continue

            total_delta = profile.pace_delta * stint_laps
            avg_delta = profile.pace_delta

            plans.append(FuelPlan(
                stint_laps=stint_laps,
                engine_mode=mode,
                fuel_start_kg=starting_fuel,
                fuel_end_kg=fuel_end,
                fuel_consumed_kg=fuel_consumed,
                total_time_delta=total_delta,
                avg_lap_time_delta=avg_delta,
            ))

        # Sort by total time delta (fastest first)
        plans.sort(key=lambda p: p.total_time_delta)
        return plans

    def optimize_race_fuel(
        self,
        race_laps: int,
        num_stops: int,
        stint_lengths: list[int],
        starting_fuel: float | None = None,
    ) -> RaceFuelStrategy:
        """Optimize fuel strategy for entire race."""
        if starting_fuel is None:
            starting_fuel = self.fuel_tank_capacity

        # Distribute fuel across stints
        stint_plans = []
        current_fuel = starting_fuel

        for i, stint_laps in enumerate(stint_lengths):
            is_last = (i == len(stint_lengths) - 1)
            target_end = self.min_fuel_reserve if is_last else max(self.min_fuel_reserve, 5.0)

            plans = self.optimize_stint_fuel(
                stint_laps, current_fuel, target_end,
                allow_rich=(i == 0),  # Allow rich only first stint
                allow_overtake=False,
            )

            if not plans:
                # Fallback to lean
                plans = self.optimize_stint_fuel(
                    stint_laps, current_fuel, target_end,
                    allow_rich=False, allow_overtake=False,
                )

            best_plan = plans[0]
            stint_plans.append(best_plan)
            current_fuel = best_plan.fuel_end_kg

        total_consumed = sum(p.fuel_consumed_kg for p in stint_plans)
        total_delta = sum(p.total_time_delta for p in stint_plans)
        mode_sequence = [p.engine_mode for p in stint_plans]

        return RaceFuelStrategy(
            starting_fuel_kg=starting_fuel,
            stint_plans=stint_plans,
            total_fuel_consumed=total_consumed,
            total_time_delta=total_delta,
            engine_mode_sequence=mode_sequence,
        )

    def calculate_fuel_for_laps(
        self,
        laps: int,
        engine_mode: EngineMode,
    ) -> float:
        """Calculate fuel needed for given laps at engine mode."""
        profile = self.engine_modes[engine_mode]
        return self.base_fuel_consumption * profile.fuel_multiplier * laps

    def calculate_max_laps_on_fuel(
        self,
        fuel_kg: float,
        engine_mode: EngineMode,
        reserve: float | None = None,
    ) -> int:
        """Calculate maximum laps possible with given fuel."""
        if reserve is None:
            reserve = self.min_fuel_reserve

        usable_fuel = fuel_kg - reserve
        if usable_fuel <= 0:
            return 0

        profile = self.engine_modes[engine_mode]
        consumption = self.base_fuel_consumption * profile.fuel_multiplier
        return int(usable_fuel / consumption)

    def simulate_fuel_effect_on_pace(
        self,
        base_lap_time: float,
        fuel_kg: float,
        fuel_per_lap: float,
        laps: int,
    ) -> list[float]:
        """Simulate lap times with decreasing fuel load."""
        lap_times = []
        current_fuel = fuel_kg

        for lap in range(laps):
            # Fuel effect: ~0.035s per 10kg (F1 approximation)
            fuel_effect = (current_fuel - self.fuel_tank_capacity / 2) * 0.0035
            lap_time = base_lap_time + fuel_effect
            lap_times.append(lap_time)
            current_fuel -= fuel_per_lap

        return lap_times


class AdaptiveFuelManager:
    """Manages fuel strategy adaptively during race."""

    def __init__(self, optimizer: FuelStrategyOptimizer):
        self.optimizer = optimizer
        self.current_plan: RaceFuelStrategy | None = None
        self.current_stint_idx = 0
        self.laps_in_current_stint = 0

    def set_strategy(self, plan: RaceFuelStrategy):
        self.current_plan = plan
        self.current_stint_idx = 0
        self.laps_in_current_stint = 0

    def get_current_mode(self) -> EngineMode:
        if not self.current_plan or self.current_stint_idx >= len(self.current_plan.stint_plans):
            return EngineMode.STANDARD
        return self.current_plan.stint_plans[self.current_stint_idx].engine_mode

    def get_target_fuel(self) -> float:
        if not self.current_plan or self.current_stint_idx >= len(self.current_plan.stint_plans):
            return self.optimizer.min_fuel_reserve
        return self.current_plan.stint_plans[self.current_stint_idx].fuel_end_kg

    def on_lap_complete(self, fuel_remaining: float) -> dict[str, Any]:
        """Call after each lap to get adaptive recommendations."""
        if not self.current_plan:
            return {"mode": EngineMode.STANDARD, "action": "continue"}

        plan = self.current_plan.stint_plans[self.current_stint_idx]
        self.laps_in_current_stint += 1

        laps_remaining = plan.stint_laps - self.laps_in_current_stint
        fuel_needed = self.optimizer.calculate_fuel_for_laps(
            laps_remaining, plan.engine_mode
        )

        result = {
            "mode": plan.engine_mode,
            "action": "continue",
            "fuel_remaining": fuel_remaining,
            "fuel_target": plan.fuel_end_kg,
            "laps_remaining_in_stint": laps_remaining,
        }

        # Check if we need to adjust mode
        if fuel_remaining < fuel_needed + self.optimizer.min_fuel_reserve:
            # Need to save fuel
            if plan.engine_mode != EngineMode.LEAN:
                result["mode"] = EngineMode.LEAN
                result["action"] = "save_fuel"
                result["reason"] = "Fuel below target, switching to lean"

        # Check if we can push harder
        elif fuel_remaining > fuel_needed + 3.0 and plan.engine_mode == EngineMode.STANDARD:
            if laps_remaining <= 5:  # Last few laps of stint
                result["mode"] = EngineMode.RICH
                result["action"] = "push"
                result["reason"] = "Fuel surplus, pushing hard to end of stint"

        return result

    def on_pit_stop(self, new_fuel_kg: float):
        """Call after pit stop to advance to next stint."""
        self.current_stint_idx += 1
        self.laps_in_current_stint = 0


def create_fuel_strategy_for_stints(
    stint_lengths: list[int],
    starting_fuel: float = 110.0,
    base_consumption: float = 1.8,
) -> RaceFuelStrategy:
    """Convenience function to create fuel strategy."""
    optimizer = FuelStrategyOptimizer(base_fuel_consumption=base_consumption)
    return optimizer.optimize_race_fuel(
        race_laps=sum(stint_lengths),
        num_stops=len(stint_lengths) - 1,
        stint_lengths=stint_lengths,
        starting_fuel=starting_fuel,
    )
