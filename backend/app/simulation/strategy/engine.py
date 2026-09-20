from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

from app.simulation.models.strategy import (
    StrategyType,
    StrategyOption,
    StrategyEvaluation,
    RaceStrategy,
    PitStopModel,
    DEFAULT_PIT_STOP_MODEL,
)
from app.simulation.models.tyre import (
    TyreCompound,
    CompoundType,
    DEFAULT_COMPOUNDS,
    get_standard_tyre_specs,
)
from app.simulation.models.track import Track
from app.simulation.models.car import Car, Engine
from app.simulation.models.driver import Driver


@dataclass
class StintPlan:
    """A single stint in a strategy."""
    compound: str
    laps: int
    fuel_start_kg: float
    engine_mode: str  # "rich", "standard", "lean"
    tyre_age_start: int = 0
    estimated_lap_times: list[float] | None = None
    total_time: float = 0.0


@dataclass
class StrategyContext:
    """Context for strategy generation."""
    track: Track
    car: Car
    engine: Engine
    driver: Driver
    race_laps: int
    pit_lane_time_loss: float  # Track-specific pit lane time loss
    available_compounds: list[TyreCompound]
    starting_compound: str
    starting_fuel_kg: float
    fuel_tank_capacity: float = 110.0
    team_pit_skill: float = 50.0
    weather_forecast: dict | None = None
    safety_car_probability: float = 0.1
    track_evolution_rate: float = 0.02  # sec/lap improvement


class StrategyEngine:
    """Generates and evaluates race strategy options."""

    ENGINE_MODES = {
        "rich": {"fuel_mult": 1.10, "pace_mult": 0.995, "tyre_deg_mult": 1.05},
        "standard": {"fuel_mult": 1.00, "pace_mult": 1.000, "tyre_deg_mult": 1.00},
        "lean": {"fuel_mult": 0.90, "pace_mult": 1.008, "tyre_deg_mult": 0.95},
    }

    def __init__(
        self,
        pit_stop_model: PitStopModel | None = None,
        compounds: dict[str, TyreCompound] | None = None,
    ):
        self.pit_stop_model = pit_stop_model or DEFAULT_PIT_STOP_MODEL
        self.compounds = compounds or DEFAULT_COMPOUNDS
        self.rng = np.random.default_rng()
        self._evaluator = None

    @property
    def evaluator(self):
        """Lazy-load strategy evaluator."""
        if self._evaluator is None:
            from app.simulation.strategy.evaluator import StrategyEvaluator
            from app.simulation.strategy.fuel import FuelStrategyOptimizer
            from app.simulation.strategy.pitstop import PitStopStrategyEngine
            self._evaluator = StrategyEvaluator(
                strategy_engine=self,
                fuel_optimizer=FuelStrategyOptimizer(),
                pit_engine=PitStopStrategyEngine(),
            )
        return self._evaluator

    def _spec_for(self, compound_name: str):
        """Resolve a compound name to its TyreSpec (enum- or string-keyed dicts)."""
        if compound_name in self.compounds:
            return self.compounds[compound_name]
        try:
            key = TyreCompound(compound_name)
        except Exception:
            key = None
        if key is not None and key in self.compounds:
            return self.compounds[key]
        specs = get_standard_tyre_specs()
        if key is not None and key in specs:
            return specs[key]
        return next(iter(self.compounds.values()))

    @staticmethod
    def _optimal_laps(spec) -> int:
        """Optimal stint length with backward-compatible field names."""
        return int(getattr(spec, "optimal_lap_count", getattr(spec, "max_life_laps", 20)))

    @staticmethod
    def _spec_display_name(spec, fallback: str) -> str:
        compound = getattr(spec, "compound", None)
        value = getattr(compound, "value", None)
        return str(value).lower() if value else fallback

    def generate_strategy_options(
        self,
        context: StrategyContext,
        max_stops: int = 3,
        min_stint_laps: int = 8,
        max_stint_laps: int | None = None,
    ) -> list[StrategyOption]:
        """Generate all viable strategy options for a race."""
        options = []

        # Determine max stint length based on tyre life
        if max_stint_laps is None:
            max_stint_laps = self._estimate_max_stint(context)

        # Generate strategies for each stop count
        for num_stops in range(max_stops + 1):
            strategy_type = self._stops_to_type(num_stops)
            stint_options = self._generate_stint_combinations(
                context, num_stops, min_stint_laps, max_stint_laps
            )

            for stint_plan in stint_options:
                option = self._build_strategy_option(
                    context, strategy_type, stint_plan
                )
                if option.is_feasible:
                    options.append(option)

        return options

    def _estimate_max_stint(self, context: StrategyContext) -> int:
        """Estimate maximum viable stint length based on hardest compound."""
        hard_compound = min(
            context.available_compounds,
            key=lambda c: c.degradation_rate
        )
        # Rough estimate: tyre lasts until degradation reaches ~2.5s/lap
        max_laps = int(2.0 / hard_compound.degradation_rate * 50)
        return min(max_laps, context.race_laps)

    def _stops_to_type(self, stops: int) -> StrategyType:
        mapping = {
            0: StrategyType.ZERO_STOP,
            1: StrategyType.ONE_STOP,
            2: StrategyType.TWO_STOP,
            3: StrategyType.THREE_STOP,
        }
        return mapping.get(stops, StrategyType.FLEXIBLE)

    def _generate_stint_combinations(
        self,
        context: StrategyContext,
        num_stops: int,
        min_laps: int,
        max_laps: int,
    ) -> list[list[StintPlan]]:
        """Generate all valid stint combinations for a given stop count."""
        num_stints = num_stops + 1
        combinations = []

        # Get available compounds for race (exclude wet/inter unless rain forecast)
        # available_compounds may hold TyreSpec objects or TyreCompound enums;
        # normalize to (name, type) pairs for backward compatibility.
        def _compound_info(c: Any) -> tuple[str, Any]:
            spec = getattr(c, "compound", c)
            name = getattr(spec, "value", str(spec)).lower()
            ctype = getattr(c, "compound_type", spec)
            return name, ctype

        race_compounds = [
            c for c in context.available_compounds
            if _compound_info(c)[1] in (CompoundType.SOFT, CompoundType.MEDIUM, CompoundType.HARD)
        ]

        if not race_compounds:
            race_compounds = context.available_compounds

        def backtrack(remaining_laps: int, stint_idx: int, current_stints: list[StintPlan]):
            if stint_idx == num_stints:
                if remaining_laps == 0:
                    combinations.append(current_stints.copy())
                return

            is_last_stint = (stint_idx == num_stints - 1)
            max_for_this = remaining_laps if is_last_stint else min(max_laps, remaining_laps - min_laps * (num_stints - stint_idx - 1))  # noqa: E501

            for laps in range(min_laps, max_for_this + 1):
                for compound in race_compounds:
                    compound_name, _ = _compound_info(compound)
                    # Must use at least 2 different compounds in race (F1 rule)
                    if stint_idx == 0:
                        if compound_name != context.starting_compound:
                            continue
                    else:
                        used_compounds = {s.compound for s in current_stints}
                        # Encourage compound variety
                        pass

                    for engine_mode in self.ENGINE_MODES.keys():
                        # Fuel calculation
                        fuel_per_lap = context.engine.fuel_burn_rate_base * self.ENGINE_MODES[engine_mode]["fuel_mult"]  # noqa: E501
                        fuel_needed = laps * fuel_per_lap + 2.0  # 2kg reserve

                        if stint_idx == 0:
                            fuel_start = context.starting_fuel_kg
                        else:
                            fuel_start = fuel_needed

                        stint = StintPlan(
                            compound=compound_name,
                            laps=laps,
                            fuel_start_kg=fuel_start,
                            engine_mode=engine_mode,
                            tyre_age_start=0 if stint_idx == 0 else 0,  # Fresh tyres each stint
                        )
                        current_stints.append(stint)
                        backtrack(remaining_laps - laps, stint_idx + 1, current_stints)
                        current_stints.pop()

        backtrack(context.race_laps, 0, [])
        return combinations

    def _build_strategy_option(
        self,
        context: StrategyContext,
        strategy_type: StrategyType,
        stints: list[StintPlan],
    ) -> StrategyOption:
        """Build a StrategyOption from stint plans with time estimation."""
        strategy_id = f"{strategy_type.value}_{'_'.join(f'{s.compound[0]}{s.laps}' for s in stints)}"  # noqa: E501

        # Check compound usage rules (must use 2 compounds unless wet)
        compounds_used = {s.compound for s in stints}
        is_wet_race = any(
            self._spec_for(c).compound_type in (CompoundType.INTERMEDIATE, CompoundType.WET)
            for c in compounds_used
        )

        feasibility_issues = []
        if not is_wet_race and len(compounds_used) < 2:
            feasibility_issues.append("Must use at least 2 dry compounds")

        # Estimate lap times for each stint
        total_time = 0.0
        total_pit_time_loss = 0.0
        all_lap_times = []

        for i, stint in enumerate(stints):
            compound_obj = self._spec_for(stint.compound)
            stint_times = self._estimate_stint_lap_times(
                context, stint, compound_obj, i, len(stints)
            )
            stint.estimated_lap_times = stint_times
            stint.total_time = sum(stint_times)
            total_time += stint.total_time
            all_lap_times.extend(stint_times)

            # Add pit stop time loss (except after last stint)
            if i < len(stints) - 1:
                next_compound = stints[i + 1].compound
                pit_loss = estimate_pit_stop_loss(
                    context.pit_lane_time_loss,
                    next_compound,
                    context.team_pit_skill,
                    self.rng,
                )
                total_pit_time_loss += pit_loss
                total_time += pit_loss

        # Risk assessment
        risk_score, risk_factors = self._assess_risk(context, stints, all_lap_times)

        # Sensitivity analysis
        sensitivity = self._calculate_sensitivity(context, stints)

        # Compound usage summary
        compounds_used_dict = {c: sum(1 for s in stints if s.compound == c) for c in compounds_used}
        sets_required = {c: 1 for c in compounds_used}  # 1 set per stint typically

        return StrategyOption(
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            stints=[
                {
                    "compound": s.compound,
                    "laps": s.laps,
                    "fuel_start": s.fuel_start_kg,
                    "engine_mode": s.engine_mode,
                    "estimated_time": s.total_time,
                    "avg_lap_time": s.total_time / s.laps if s.laps > 0 else 0,
                }
                for s in stints
            ],
            total_estimated_time=total_time,
            total_pit_time_loss=total_pit_time_loss,
            risk_score=risk_score,
            risk_factors=risk_factors,
            sensitivity_to_safety_car=sensitivity["safety_car"],
            sensitivity_to_rain=sensitivity["rain"],
            sensitivity_to_degradation=sensitivity["degradation"],
            sensitivity_to_traffic=sensitivity["traffic"],
            compounds_used=compounds_used_dict,
            sets_required=sets_required,
            is_feasible=len(feasibility_issues) == 0,
            feasibility_issues=feasibility_issues,
        )

    def _estimate_stint_lap_times(
        self,
        context: StrategyContext,
        stint: StintPlan,
        compound: TyreCompound,
        stint_idx: int,
        total_stints: int,
    ) -> list[float]:
        """Estimate lap times for a stint."""
        lap_times = []
        base_lap_time = self._estimate_base_lap_time(context, compound, stint.fuel_start_kg)

        engine_mode = self.ENGINE_MODES[stint.engine_mode]
        pace_mult = engine_mode["pace_mult"]
        deg_mult = engine_mode["tyre_deg_mult"]

        for lap_in_stint in range(stint.laps):
            tyre_age = stint.tyre_age_start + lap_in_stint

            # Degradation
            deg = compound.degradation_rate * deg_mult * tyre_age
            # Non-linear deg curve
            optimal_laps = self._optimal_laps(compound)
            if tyre_age > optimal_laps:
                deg *= 1.5 + (tyre_age - optimal_laps) * 0.1

            # Fuel effect (lighter = faster)
            fuel_kg = stint.fuel_start_kg - lap_in_stint * context.engine.fuel_burn_rate_base * engine_mode["fuel_mult"]  # noqa: E501
            fuel_effect = (fuel_kg - context.fuel_tank_capacity / 2) * 0.008  # ~0.008s/kg

            # Track evolution
            total_laps_before = sum(s.laps for s in [stint] if False)  # simplified
            track_evo = -context.track_evolution_rate * (stint_idx * 20 + lap_in_stint)  # improves over race  # noqa: E501

            lap_time = base_lap_time * pace_mult + deg + fuel_effect + track_evo
            lap_times.append(lap_time)

        return lap_times

    def _estimate_base_lap_time(
        self,
        context: StrategyContext,
        compound: TyreCompound,
        fuel_kg: float,
    ) -> float:
        """Estimate base lap time for a compound at given fuel."""
        # Simplified: use compound base performance + track grip + car aero
        base = 80.0  # Base lap time in seconds

        # Compound pace delta (softer = faster)
        compound_pace = {
            CompoundType.SOFT: -0.8,
            CompoundType.MEDIUM: 0.0,
            CompoundType.HARD: 0.7,
            CompoundType.INTERMEDIATE: 2.5,
            CompoundType.WET: 5.0,
        }
        base += compound_pace.get(compound.compound_type, 0.0)

        # Track reference pace (use reference lap time as anchor)
        base += (context.track.reference_lap_time - 90.0) * 0.5

        # Car performance
        base -= (getattr(context.car, "aero_efficiency", 50) - 50) * 0.05
        base -= (getattr(context.engine, "peak_power_kw", 780) - 780) * 0.001

        # Driver skill
        skill = getattr(context.driver, "race_skill", getattr(context.driver, "overall_skill", 50))
        base -= (skill - 50) * 0.03

        # Fuel weight
        base += (fuel_kg - 50) * 0.008

        return base

    def _assess_risk(
        self,
        context: StrategyContext,
        stints: list[StintPlan],
        all_lap_times: list[float],
    ) -> tuple[float, list[str]]:
        """Assess strategy risk."""
        risk_score = 0.0
        risk_factors = []

        # Long stint risk
        for stint in stints:
            compound = self._spec_for(stint.compound)
            optimal_laps = self._optimal_laps(compound)
            display = self._spec_display_name(compound, stint.compound)
            if stint.laps > optimal_laps * 1.3:
                risk_score += 15
                risk_factors.append(f"Long stint on {display} ({stint.laps} laps)")

            if stint.laps > optimal_laps * 1.6:
                risk_score += 25
                risk_factors.append(f"Very long stint on {display} - high degradation risk")

        # Compound variety risk
        compounds_used = {s.compound for s in stints}
        if len(compounds_used) == 1:
            risk_score += 20
            risk_factors.append("Single compound strategy - no flexibility")

        # Soft tyre risk
        if "soft" in compounds_used:
            soft_stints = [s for s in stints if s.compound == "soft"]
            for s in soft_stints:
                if s.laps > 15:
                    risk_score += 10
                    risk_factors.append("Extended soft tyre stint")

        # Number of stops risk
        if len(stints) >= 4:
            risk_score += 15
            risk_factors.append("High number of pit stops - traffic/issue risk")

        # Weather risk
        if context.weather_forecast and context.weather_forecast.get("rain_probability", 0) > 0.3:
            risk_score += 10
            risk_factors.append("Rain forecast - strategy may need adaptation")

        return min(risk_score, 100.0), risk_factors

    def _calculate_sensitivity(
        self,
        context: StrategyContext,
        stints: list[StintPlan],
    ) -> dict[str, float]:
        """Calculate strategy sensitivity to various factors."""
        num_stops = len(stints) - 1

        return {
            "safety_car": -0.15 * num_stops,  # More stops = more SC benefit
            "rain": 0.2 if any(s.compound in ["soft", "medium"] for s in stints) else -0.1,
            "degradation": 0.15 * num_stops,  # More stops = more sensitive to deg
            "traffic": 0.1 * num_stops,  # More stops = more traffic exposure
        }

    def evaluate_strategy(
        self,
        option: StrategyOption,
        context: StrategyContext,
        competitor_strategies: list[StrategyOption] | None = None,
    ) -> StrategyEvaluation:
        """Evaluate a strategy option in detail."""
        all_lap_times = []
        for stint_data in option.stints:
            stint_times = self._estimate_stint_lap_times(
                context,
                StintPlan(
                    compound=stint_data["compound"],
                    laps=stint_data["laps"],
                    fuel_start_kg=stint_data["fuel_start"],
                    engine_mode=stint_data.get("engine_mode", "standard"),
                ),
                self._spec_for(stint_data["compound"]),
                0, len(option.stints)
            )
            all_lap_times.extend(stint_times)

        avg_lap = sum(all_lap_times) / len(all_lap_times) if all_lap_times else 0
        best_lap = min(all_lap_times) if all_lap_times else 0

        # Tyre life margin
        tyre_life_margin = {}
        for stint_data in option.stints:
            compound = self._spec_for(stint_data["compound"])
            margin = self._optimal_laps(compound) - stint_data["laps"]
            tyre_life_margin[stint_data["compound"]] = margin

        # Scenario analysis
        scenario_results = {}
        if context.safety_car_probability > 0.05:
            sc_time_loss = self._simulate_safety_car_impact(option, context)
            scenario_results["safety_car"] = {"time_loss": sc_time_loss, "position_change": -sc_time_loss / avg_lap * 0.5}  # noqa: E501

        if context.weather_forecast and context.weather_forecast.get("rain_probability", 0) > 0.2:
            rain_time_loss = self._simulate_rain_impact(option, context)
            scenario_results["rain"] = {"time_loss": rain_time_loss, "position_change": -rain_time_loss / avg_lap * 0.5}  # noqa: E501

        # Degradation sensitivity
        high_deg_loss = self._simulate_high_degradation(option, context)
        scenario_results["high_deg"] = {"time_loss": high_deg_loss, "position_change": -high_deg_loss / avg_lap * 0.5}  # noqa: E501

        return StrategyEvaluation(
            strategy=option,
            expected_position=0.0,  # Will be set by race simulation
            position_range=(1, 20),
            win_probability=0.0,
            podium_probability=0.0,
            points_expectation=0.0,
            avg_lap_time=avg_lap,
            best_lap_time=best_lap,
            tyre_life_margin=tyre_life_margin,
            scenario_results=scenario_results,
        )

    def _simulate_safety_car_impact(self, option: StrategyOption, context: StrategyContext) -> float:  # noqa: E501
        """Estimate time loss/gain from safety car."""
        # Strategies with recent pit stops benefit from SC
        # Strategies about to pit lose out
        return self.rng.uniform(-5.0, 5.0)  # Placeholder

    def _simulate_rain_impact(self, option: StrategyOption, context: StrategyContext) -> float:
        """Estimate impact of rain."""
        # Strategies on intermediates/wets benefit
        has_wet = any(
            self._spec_for(s["compound"]).compound_type in (CompoundType.INTERMEDIATE, CompoundType.WET)  # noqa: E501
            for s in option.stints
        )
        if has_wet:
            return self.rng.uniform(-10.0, 0.0)
        return self.rng.uniform(5.0, 20.0)

    def _simulate_high_degradation(self, option: StrategyOption, context: StrategyContext) -> float:
        """Estimate impact of higher than expected degradation."""
        extra_deg = 0.0
        for stint_data in option.stints:
            compound = self._spec_for(stint_data["compound"])
            optimal_laps = self._optimal_laps(compound)
            if stint_data["laps"] > optimal_laps:
                extra_deg += (stint_data["laps"] - optimal_laps) * 0.3
        return extra_deg

    def rank_strategies(
        self,
        options: list[StrategyOption],
        context: StrategyContext,
    ) -> list[tuple[StrategyOption, float]]:
        """Rank strategies by total estimated time (lower is better)."""
        ranked = []
        for opt in options:
            eval_result = self.evaluate_strategy(opt, context)
            # Score = total time + risk penalty
            score = opt.total_estimated_time + opt.risk_score * 0.1
            ranked.append((opt, score))

        ranked.sort(key=lambda x: x[1])
        return ranked


def estimate_pit_stop_loss(
    track_pit_lane_time: float,
    compound: str,
    team_pit_skill: float,
    rng: Any = None,
) -> float:
    """Quick estimate of pit stop time loss."""
    if rng is None:
        rng = np.random.default_rng()

    team_factor = 1.1 - (team_pit_skill / 100) * 0.15
    stationary = rng.normal(2.4 * team_factor, 0.15 * team_factor)
    stationary = max(1.8, stationary)

    compound_mod = {"soft": 1.0, "medium": 1.0, "hard": 1.0, "intermediate": 1.02, "wet": 1.02}
    stationary *= compound_mod.get(compound, 1.0)

    if rng.random() < 0.02:
        stationary += rng.uniform(1.0, 5.0)

    return track_pit_lane_time + stationary
