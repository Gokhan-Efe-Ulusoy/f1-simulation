from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

from app.simulation.models.strategy import (
    StrategyOption,
    StrategyEvaluation,
    StrategyType,
    RaceStrategy,
)
from app.simulation.strategy.engine import StrategyEngine, StrategyContext, StintPlan
from app.simulation.strategy.fuel import FuelStrategyOptimizer, RaceFuelStrategy
from app.simulation.strategy.pitstop import PitStopStrategyEngine
from app.simulation.models.track import Track
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.tyre import TyreCompound, CompoundType, DEFAULT_COMPOUNDS


@dataclass
class StrategyComparison:
    """Comparison between two strategies."""
    strategy_a: StrategyOption
    strategy_b: StrategyOption
    time_difference: float  # A - B (positive = B faster)
    position_difference: float  # Expected position difference
    key_advantages_a: list[str]
    key_advantages_b: list[str]
    risk_comparison: dict[str, float]  # factor -> difference (A - B)
    scenario_sensitivity: dict[str, float]  # scenario -> time diff


@dataclass
class StrategyRecommendation:
    """Final strategy recommendation."""
    recommended: StrategyOption
    alternatives: list[StrategyOption]
    reasoning: list[str]
    confidence: float
    contingency_plans: dict[str, StrategyOption]  # scenario -> backup strategy


class StrategyEvaluator:
    """Evaluates and compares strategy options comprehensively."""

    def __init__(
        self,
        strategy_engine: StrategyEngine | None = None,
        fuel_optimizer: FuelStrategyOptimizer | None = None,
        pit_engine: PitStopStrategyEngine | None = None,
    ):
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.fuel_optimizer = fuel_optimizer or FuelStrategyOptimizer()
        self.pit_engine = pit_engine or PitStopStrategyEngine()
        self.rng = np.random.default_rng()

    def evaluate_all_strategies(
        self,
        context: StrategyContext,
        max_stops: int = 3,
    ) -> list[tuple[StrategyOption, StrategyEvaluation]]:
        """Generate and evaluate all viable strategies."""
        options = self.strategy_engine.generate_strategy_options(context, max_stops)
        evaluations = []

        for opt in options:
            eval_result = self.strategy_engine.evaluate_strategy(opt, context)
            evaluations.append((opt, eval_result))

        # Sort by total estimated time
        evaluations.sort(key=lambda x: x[0].total_estimated_time)
        return evaluations

    def compare_strategies(
        self,
        strategy_a: StrategyOption,
        strategy_b: StrategyOption,
        context: StrategyContext,
    ) -> StrategyComparison:
        """Compare two strategies in detail."""
        eval_a = self.strategy_engine.evaluate_strategy(strategy_a, context)
        eval_b = self.strategy_engine.evaluate_strategy(strategy_b, context)

        time_diff = strategy_a.total_estimated_time - strategy_b.total_estimated_time

        # Position difference estimate (rough: 1 position ~ 0.3-0.5s over race)
        position_diff = time_diff / 0.4

        # Key advantages
        adv_a = self._identify_advantages(strategy_a, strategy_b, context)
        adv_b = self._identify_advantages(strategy_b, strategy_a, context)

        # Risk comparison
        risk_factors = [
            "safety_car", "rain", "degradation", "traffic",
            "track_position", "tyre_life", "fuel_margin"
        ]
        risk_comp = {}
        for factor in risk_factors:
            sens_a = getattr(eval_a.strategy, f"sensitivity_to_{factor}", 0)
            sens_b = getattr(eval_b.strategy, f"sensitivity_to_{factor}", 0)
            risk_comp[factor] = sens_a - sens_b

        # Scenario sensitivity
        scenario_sens = {}
        for scenario in ["safety_car", "rain", "high_deg"]:
            loss_a = eval_a.scenario_results.get(scenario, {}).get("time_loss", 0)
            loss_b = eval_b.scenario_results.get(scenario, {}).get("time_loss", 0)
            scenario_sens[scenario] = loss_a - loss_b

        return StrategyComparison(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            time_difference=time_diff,
            position_difference=position_diff,
            key_advantages_a=adv_a,
            key_advantages_b=adv_b,
            risk_comparison=risk_comp,
            scenario_sensitivity=scenario_sens,
        )

    def _identify_advantages(
        self,
        strategy: StrategyOption,
        other: StrategyOption,
        context: StrategyContext,
    ) -> list[str]:
        """Identify key advantages of strategy over other."""
        advantages = []

        # Fewer stops
        if len(strategy.stints) < len(other.stints):
            advantages.append(f"Fewer pit stops ({len(strategy.stints)-1} vs {len(other.stints)-1})")  # noqa: E501

        # Better tyre life
        for s in strategy.stints:
            compound = s["compound"]
            laps = s["laps"]
            # Would need compound info to check life
            pass

        # Track position sensitivity
        if strategy.sensitivity_to_traffic < other.sensitivity_to_traffic:
            advantages.append("Less sensitive to traffic")

        # Safety car benefit
        if strategy.sensitivity_to_safety_car < other.sensitivity_to_safety_car:
            advantages.append("Benefits more from safety car")

        # Rain benefit
        if strategy.sensitivity_to_rain < other.sensitivity_to_rain:
            advantages.append("Better in wet conditions")

        # Degradation robustness
        if strategy.sensitivity_to_degradation < other.sensitivity_to_degradation:
            advantages.append("More robust to high degradation")

        return advantages

    def recommend_strategy(
        self,
        context: StrategyContext,
        max_stops: int = 3,
        driver_position: int = 10,
        championship_situation: str = "normal",  # "normal", "need_points", "need_win"
    ) -> StrategyRecommendation:
        """Recommend best strategy with reasoning."""
        evaluations = self.evaluate_all_strategies(context, max_stops)

        if not evaluations:
            raise ValueError("No viable strategies found")

        # Score strategies
        scored = []
        for opt, eval_result in evaluations:
            score = self._calculate_strategy_score(
                opt, eval_result, context, driver_position, championship_situation
            )
            scored.append((opt, eval_result, score))

        scored.sort(key=lambda x: x[2])  # Lower score = better

        recommended = scored[0][0]
        alternatives = [s[0] for s in scored[1:4]]
        reasoning = self._generate_reasoning(scored[0], context, championship_situation)
        confidence = self._calculate_confidence(scored)

        # Contingency plans
        contingencies = self._generate_contingencies(scored, context)

        return StrategyRecommendation(
            recommended=recommended,
            alternatives=alternatives,
            reasoning=reasoning,
            confidence=confidence,
            contingency_plans=contingencies,
        )

    def _calculate_strategy_score(
        self,
        option: StrategyOption,
        evaluation: StrategyEvaluation,
        context: StrategyContext,
        position: int,
        situation: str,
    ) -> float:
        """Calculate composite strategy score (lower is better)."""
        score = option.total_estimated_time

        # Risk penalty
        score += option.risk_score * 0.15

        # Position-based adjustments
        if position <= 3:  # Front runners
            # Prefer strategies with track position control
            score += option.sensitivity_to_traffic * 2.0
            score -= option.sensitivity_to_safety_car * 1.0
        elif position >= 15:  # Back markers
            # Can take risks, prefer different strategy
            score += option.sensitivity_to_safety_car * 0.5

        # Championship situation
        if situation == "need_win":
            # Favor aggressive strategies (fewer stops, softer tyres)
            score -= (4 - len(option.stints)) * 2.0
            for s in option.stints:
                if s["compound"] == "soft":
                    score -= 1.0
        elif situation == "need_points":
            # Favor conservative, robust strategies
            score += option.risk_score * 0.1
            score += option.sensitivity_to_degradation * 1.5

        # Weather
        if context.weather_forecast:
            rain_prob = context.weather_forecast.get("rain_probability", 0)
            if rain_prob > 0.3:
                score += option.sensitivity_to_rain * 5.0

        return score

    def _generate_reasoning(
        self,
        best: tuple[StrategyOption, StrategyEvaluation, float],
        context: StrategyContext,
        situation: str,
    ) -> list[str]:
        """Generate human-readable reasoning for recommendation."""
        opt, eval_result, score = best
        reasons = []

        reasons.append(
            f"Fastest overall time: {opt.total_estimated_time:.1f}s "
            f"({opt.strategy_type.value}, {len(opt.stints)-1} stops)"
        )

        if opt.risk_score < 20:
            reasons.append("Low risk strategy with good tyre life margins")
        elif opt.risk_score < 40:
            reasons.append("Moderate risk - manageable with good pace")
        else:
            reasons.append("Higher risk but potential for high reward")

        # Compound reasoning
        compounds = [s["compound"] for s in opt.stints]
        reasons.append(f"Compound sequence: {' -> '.join(compounds)}")

        # Situation-specific
        if situation == "need_win":
            reasons.append("Aggressive strategy chosen to maximize win probability")
        elif situation == "need_points":
            reasons.append("Conservative strategy to secure points finish")

        # Weather
        if context.weather_forecast and context.weather_forecast.get("rain_probability", 0) > 0.3:
            reasons.append("Strategy accounts for rain risk")

        return reasons

    def _calculate_confidence(self, scored: list) -> float:
        """Calculate confidence in recommendation."""
        if len(scored) < 2:
            return 0.9

        best_score = scored[0][2]
        second_score = scored[1][2]
        gap = second_score - best_score

        # Normalize: 5s gap = high confidence
        confidence = min(0.5 + gap / 10.0, 0.95)
        return confidence

    def _generate_contingencies(
        self,
        scored: list,
        context: StrategyContext,
    ) -> dict[str, StrategyOption]:
        """Generate contingency plans for different scenarios."""
        contingencies = {}

        # Safety car contingency - favor strategy that benefits from SC
        sc_best = min(scored, key=lambda x: x[0].sensitivity_to_safety_car)
        contingencies["safety_car"] = sc_best[0]

        # Rain contingency
        rain_best = min(scored, key=lambda x: x[0].sensitivity_to_rain)
        contingencies["rain"] = rain_best[0]

        # High degradation contingency
        deg_best = min(scored, key=lambda x: x[0].sensitivity_to_degradation)
        contingencies["high_degradation"] = deg_best[0]

        # Late race attack
        attack_best = min(scored[:3], key=lambda x: len(x[0].stints))  # Fewest stops
        contingencies["late_attack"] = attack_best[0]

        return contingencies

    def simulate_strategy_battle(
        self,
        strategy_a: StrategyOption,
        strategy_b: StrategyOption,
        context: StrategyContext,
        num_simulations: int = 100,
    ) -> dict[str, Any]:
        """Monte Carlo simulation of strategy battle."""
        results = {
            "a_wins": 0,
            "b_wins": 0,
            "avg_time_diff": 0.0,
            "time_diff_distribution": [],
            "scenario_outcomes": {},
        }

        for _ in range(num_simulations):
            # Add noise to lap times
            time_a = strategy_a.total_estimated_time
            time_b = strategy_b.total_estimated_time

            # Random variation (±0.5s per stint)
            for _ in strategy_a.stints:
                time_a += self.rng.normal(0, 0.3)
            for _ in strategy_b.stints:
                time_b += self.rng.normal(0, 0.3)

            # Random safety car
            if self.rng.random() < context.safety_car_probability:
                sc_effect_a = self.rng.uniform(-5, 5)
                sc_effect_b = self.rng.uniform(-5, 5)
                time_a += sc_effect_a
                time_b += sc_effect_b

            diff = time_a - time_b
            results["time_diff_distribution"].append(diff)

            if diff < 0:
                results["a_wins"] += 1
            else:
                results["b_wins"] += 1

        results["avg_time_diff"] = np.mean(results["time_diff_distribution"])
        results["a_win_probability"] = results["a_wins"] / num_simulations
        results["b_win_probability"] = results["b_wins"] / num_simulations

        return results


class LiveStrategyAdvisor:
    """Real-time strategy advisor during race."""

    def __init__(
        self,
        evaluator: StrategyEvaluator,
        pit_engine: PitStopStrategyEngine,
    ):
        self.evaluator = evaluator
        self.pit_engine = pit_engine
        self.current_strategy: StrategyOption | None = None
        self.current_context: StrategyContext | None = None

    def initialize_race(
        self,
        context: StrategyContext,
        starting_position: int,
    ):
        """Initialize at race start."""
        self.current_context = context
        recommendation = self.evaluator.recommend_strategy(
            context, driver_position=starting_position
        )
        self.current_strategy = recommendation.recommended
        return recommendation

    def on_lap_complete(
        self,
        driver_state: dict[str, Any],
        competitor_states: list[dict[str, Any]],
        track_position: int,
        laps_remaining: int,
    ) -> dict[str, Any]:
        """Called each lap for real-time advice."""
        if not self.current_strategy or not self.current_context:
            return {"action": "continue", "reason": "Not initialized"}

        # Check pit decision
        pit_decision = self.pit_engine.make_pit_decision(
            driver_state=driver_state,
            strategy=RaceStrategy(
                driver_id=driver_state["driver_id"],
                strategy_type=self.current_strategy.strategy_type,
                planned_stops=[
                    {"lap": sum(s["laps"] for s in self.current_strategy.stints[:i+1]),
                     "compound": s["compound"], "stint": i+1}
                    for i, s in enumerate(self.current_strategy.stints[:-1])
                ],
            ),
            competitors=competitor_states,
            track_pit_lane_loss=self.current_context.pit_lane_time_loss,
            laps_remaining=laps_remaining,
        )

        advice = {
            "pit_decision": pit_decision,
            "current_strategy": self.current_strategy.strategy_id,
            "stint_progress": self._get_stint_progress(driver_state),
            "gap_to_target": self._calculate_gaps(driver_state, competitor_states),
        }

        # Check if strategy switch needed
        if self._should_switch_strategy(driver_state, competitor_states, laps_remaining):
            advice["strategy_switch"] = self._recommend_switch(
                driver_state, competitor_states, laps_remaining
            )

        return advice

    def _get_stint_progress(self, driver_state: dict) -> dict:
        current_stint = 0
        laps_done = driver_state.get("laps_in_stint", 0)
        return {"current_stint": current_stint, "laps_in_stint": laps_done}

    def _calculate_gaps(self, driver_state: dict, competitors: list) -> dict:
        return {c["driver_id"]: c.get("gap_ahead", 0) for c in competitors}

    def _should_switch_strategy(
        self,
        driver_state: dict,
        competitors: list,
        laps_remaining: int,
    ) -> bool:
        # Check for major changes: weather, safety car, big gap changes
        return False  # Simplified

    def _recommend_switch(
        self,
        driver_state: dict,
        competitors: list,
        laps_remaining: int,
    ) -> dict:
        return {"new_strategy": "flexible", "reason": "Conditions changed"}
