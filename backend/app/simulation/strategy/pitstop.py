from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import numpy as np

from app.simulation.models.strategy import (
    PitStopType,
    PitStopEvent,
    PitStopStrategy,
    PitStopModel,
    DEFAULT_PIT_STOP_MODEL,
    estimate_pit_stop_loss,
)
from app.simulation.models.tyre import TyreCompound, CompoundType, DEFAULT_COMPOUNDS


def _optimal_laps(spec) -> int:
    """Optimal stint length with backward-compatible field names."""
    return int(getattr(spec, "optimal_lap_count", getattr(spec, "max_life_laps", 20)))


class PitStopTrigger(str, Enum):
    """Reason for pit stop trigger."""
    SCHEDULED = "scheduled"
    UNDERCUT = "undercut"
    OVERCUT = "overcut"
    SAFETY_CAR = "safety_car"
    VIRTUAL_SAFETY_CAR = "virtual_safety_car"
    INCIDENT = "incident"
    WEATHER_CHANGE = "weather_change"
    TYRE_FAILURE = "tyre_failure"
    DAMAGE = "damage"
    PENALTY = "penalty"
    TEAM_ORDER = "team_order"


@dataclass
class UndercutAnalysis:
    """Analysis of undercut opportunity."""
    target_driver_id: str
    attacker_driver_id: str
    current_gap: float  # seconds behind target
    pit_loss_attacker: float  # attacker's pit stop time loss
    pit_loss_target: float  # target's pit stop time loss (if they pit next lap)
    tyre_advantage_attacker: float  # sec/lap pace advantage on fresh tyres
    tyre_advantage_target: float  # target's pace on old tyres
    laps_to_make_up: int  # laps needed to overcome gap
    is_viable: bool
    recommended_lap: int
    confidence: float  # 0-1
    risk_factors: list[str]


@dataclass
class OvercutAnalysis:
    """Analysis of overcut opportunity."""
    target_driver_id: str
    attacker_driver_id: str
    current_gap: float  # seconds ahead of target
    target_pit_lap: int  # when target pits
    attacker_stay_out_laps: int  # how many laps attacker stays out
    target_new_tyre_pace: float  # target's pace on fresh tyres
    attacker_old_tyre_pace: float  # attacker's pace on old tyres
    track_position_value: float  # seconds value of track position
    is_viable: bool
    recommended_stay_out_laps: int
    confidence: float
    risk_factors: list[str]


@dataclass
class PitWindow:
    """Optimal pit window for a driver."""
    driver_id: str
    planned_lap: int
    earliest_lap: int
    latest_lap: int
    optimal_lap: int
    reason: str
    compounds_available: list[str]
    recommended_compound: str
    tyre_life_remaining: dict[str, int]  # compound -> laps remaining


@dataclass
class PitStopDecision:
    """Real-time pit stop decision."""
    driver_id: str
    current_lap: int
    should_pit_now: bool
    should_pit_next_lap: bool
    trigger: PitStopTrigger
    recommended_compound: str
    reason: str
    confidence: float
    alternative_options: list[dict]  # Other options with scores
    undercut_analysis: UndercutAnalysis | None = None
    overcut_analysis: OvercutAnalysis | None = None


class PitStopStrategyEngine:
    """Real-time pit stop strategy and undercut/overcut analysis."""

    def __init__(
        self,
        pit_stop_model: PitStopModel | None = None,
        compounds: dict[str, TyreCompound] | None = None,
    ):
        self.pit_stop_model = pit_stop_model or DEFAULT_PIT_STOP_MODEL
        self.compounds = compounds or DEFAULT_COMPOUNDS
        self.rng = np.random.default_rng()

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
        from app.simulation.models.tyre import get_standard_tyre_specs as _specs

        specs = _specs()
        if key is not None and key in specs:
            return specs[key]
        return next(iter(self.compounds.values()))

    def analyze_undercut(
        self,
        attacker_state: dict[str, Any],
        target_state: dict[str, Any],
        track_pit_lane_loss: float,
        laps_remaining: int,
        team_pit_skill_attacker: float = 50,
        team_pit_skill_target: float = 50,
    ) -> UndercutAnalysis:
        """
        Analyze if attacker can undercut target.
        
        Undercut: Attacker pits before target, uses fresh tyre pace to overcome gap.
        """
        attacker_gap = target_state["gap_ahead"]  # positive = attacker behind
        attacker_tyre_age = attacker_state["tyre_age"]
        attacker_compound = attacker_state["compound"]
        target_tyre_age = target_state["tyre_age"]
        target_compound = target_state["compound"]

        # Estimate pit stop time losses
        attacker_pit_loss = estimate_pit_stop_loss(
            track_pit_lane_loss, attacker_compound, team_pit_skill_attacker, self.rng
        )
        target_pit_loss = estimate_pit_stop_loss(
            track_pit_lane_loss, target_compound, team_pit_skill_target, self.rng
        )

        # Fresh tyre pace advantage (attacker on new tyres vs target on old)
        attacker_compound_obj = self._spec_for(attacker_compound)
        target_compound_obj = self._spec_for(target_compound)

        # Pace on fresh tyres for attacker
        attacker_fresh_pace = self._estimate_pace(attacker_compound_obj, 0, attacker_state.get("fuel_kg", 50))  # noqa: E501
        # Pace on old tyres for target (if they stay out one more lap)
        target_old_pace = self._estimate_pace(target_compound_obj, target_tyre_age + 1, target_state.get("fuel_kg", 50))  # noqa: E501

        tyre_advantage = target_old_pace - attacker_fresh_pace  # positive = attacker faster

        # Net gap after both pit (attacker pits this lap, target next)
        # Attacker loses pit_loss, gains tyre_advantage per lap
        # Target loses pit_loss next lap
        net_gap_after_pits = attacker_gap + attacker_pit_loss - target_pit_loss

        # Laps to make up the gap
        if tyre_advantage > 0:
            laps_to_make_up = int(np.ceil(net_gap_after_pits / tyre_advantage))
        else:
            laps_to_make_up = 999

        # Check viability
        is_viable = (
            laps_to_make_up <= laps_remaining and
            laps_to_make_up <= 10 and  # Reasonable limit
            tyre_advantage > 0.3  # Meaningful pace advantage
        )

        # Risk factors
        risk_factors = []
        if attacker_tyre_age > _optimal_laps(attacker_compound_obj):
            risk_factors.append("Attacker tyres past optimal life")
        if target_tyre_age < _optimal_laps(target_compound_obj) * 0.5:
            risk_factors.append("Target tyres still fresh - less degradation delta")
        if attacker_gap > 5.0:
            risk_factors.append("Large gap to overcome")
        if track_pit_lane_loss > 25:
            risk_factors.append("Long pit lane - high time loss")

        confidence = 1.0 - min(len(risk_factors) * 0.15, 0.7)
        if not is_viable:
            confidence *= 0.3

        return UndercutAnalysis(
            target_driver_id=target_state["driver_id"],
            attacker_driver_id=attacker_state["driver_id"],
            current_gap=attacker_gap,
            pit_loss_attacker=attacker_pit_loss,
            pit_loss_target=target_pit_loss,
            tyre_advantage_attacker=tyre_advantage,
            tyre_advantage_target=target_old_pace,
            laps_to_make_up=laps_to_make_up if is_viable else 999,
            is_viable=is_viable,
            recommended_lap=attacker_state["current_lap"] if is_viable else -1,
            confidence=confidence,
            risk_factors=risk_factors,
        )

    def analyze_overcut(
        self,
        attacker_state: dict[str, Any],
        target_state: dict[str, Any],
        track_pit_lane_loss: float,
        laps_remaining: int,
        team_pit_skill_attacker: float = 50,
        team_pit_skill_target: float = 50,
    ) -> OvercutAnalysis:
        """
        Analyze if attacker can overcut target.
        
        Overcut: Target pits first, attacker stays out longer on old tyres,
        then pits for fresh tyres and emerges ahead.
        """
        attacker_gap = attacker_state["gap_ahead"]  # positive = attacker ahead
        attacker_tyre_age = attacker_state["tyre_age"]
        attacker_compound = attacker_state["compound"]
        target_tyre_age = target_state["tyre_age"]
        target_compound = target_state["compound"]

        attacker_compound_obj = self._spec_for(attacker_compound)
        target_compound_obj = self._spec_for(target_compound)

        # Target pits now, attacker stays out
        target_pit_loss = estimate_pit_stop_loss(
            track_pit_lane_loss, target_compound, team_pit_skill_target, self.rng
        )

        # Target's pace on fresh tyres (after pit)
        target_fresh_pace = self._estimate_pace(target_compound_obj, 0, target_state.get("fuel_kg", 50))  # noqa: E501

        # Attacker's pace on old tyres (staying out)
        max_stay_out = min(5, laps_remaining)  # Max 5 laps overcut
        best_stay_out = 0
        best_net_gain = -999

        for stay_laps in range(1, max_stay_out + 1):
            attacker_old_pace = self._estimate_pace(
                attacker_compound_obj, attacker_tyre_age + stay_laps, attacker_state.get("fuel_kg", 50)  # noqa: E501
            )
            pace_delta = attacker_old_pace - target_fresh_pace  # positive = attacker slower

            # Time gained by staying out vs pitting now
            attacker_pit_loss = estimate_pit_stop_loss(
                track_pit_lane_loss, attacker_compound, team_pit_skill_attacker, self.rng
            )

            # Net: attacker saves pit loss now, but loses pace_delta per lap
            net_gain = attacker_pit_loss - pace_delta * stay_laps - target_pit_loss

            if net_gain > best_net_gain:
                best_net_gain = net_gain
                best_stay_out = stay_laps

        # Track position value (clean air advantage)
        track_position_value = 0.3 * best_stay_out  # ~0.3s/lap in clean air

        is_viable = best_net_gain + track_position_value > 0.5 and best_stay_out > 0

        risk_factors = []
        if attacker_tyre_age > _optimal_laps(attacker_compound_obj) * 1.2:
            risk_factors.append("Attacker tyres heavily degraded - pace cliff risk")
        if target_compound_obj.compound_type == CompoundType.SOFT and attacker_compound_obj.compound_type == CompoundType.HARD:  # noqa: E501
            risk_factors.append("Target on softer compound - bigger fresh tyre advantage")
        if attacker_gap < 1.0:
            risk_factors.append("Small gap - easy for target to undercut back")

        confidence = 1.0 - min(len(risk_factors) * 0.2, 0.6)
        if not is_viable:
            confidence *= 0.3

        return OvercutAnalysis(
            target_driver_id=target_state["driver_id"],
            attacker_driver_id=attacker_state["driver_id"],
            current_gap=attacker_gap,
            target_pit_lap=target_state["current_lap"],
            attacker_stay_out_laps=best_stay_out,
            target_new_tyre_pace=target_fresh_pace,
            attacker_old_tyre_pace=self._estimate_pace(
                attacker_compound_obj, attacker_tyre_age + best_stay_out, attacker_state.get("fuel_kg", 50)  # noqa: E501
            ),
            track_position_value=track_position_value,
            is_viable=is_viable,
            recommended_stay_out_laps=best_stay_out if is_viable else 0,
            confidence=confidence,
            risk_factors=risk_factors,
        )

    def _estimate_pace(
        self,
        compound: TyreCompound,
        tyre_age: int,
        fuel_kg: float,
    ) -> float:
        """Estimate lap time for compound at given age and fuel."""
        if isinstance(compound, TyreCompound):
            compound = self._spec_for(compound.value)
        base_pace = 90.0  # Base lap time

        # Compound base performance
        compound_delta = {
            CompoundType.SOFT: -0.8,
            CompoundType.MEDIUM: 0.0,
            CompoundType.HARD: 0.7,
            CompoundType.INTERMEDIATE: 3.0,
            CompoundType.WET: 6.0,
        }
        base_pace += compound_delta.get(compound.compound_type, 0.0)

        # Degradation
        deg = compound.degradation_rate * tyre_age
        if tyre_age > _optimal_laps(compound):
            deg *= 1.5 + (tyre_age - _optimal_laps(compound)) * 0.15

        # Fuel
        fuel_effect = (fuel_kg - 50) * 0.008

        return base_pace + deg + fuel_effect

    def calculate_pit_window(
        self,
        driver_state: dict[str, Any],
        strategy: PitStopStrategy,
        track_pit_lane_loss: float,
        laps_remaining: int,
        safety_car_probability: float = 0.1,
    ) -> PitWindow:
        """Calculate optimal pit window for a driver."""
        current_lap = driver_state["current_lap"]
        next_stop = strategy.get_next_stop(current_lap)

        if not next_stop:
            # No planned stops - check if should stop
            return PitWindow(
                driver_id=driver_state["driver_id"],
                planned_lap=-1,
                earliest_lap=-1,
                latest_lap=-1,
                optimal_lap=-1,
                reason="No planned stops remaining",
                compounds_available=[],
                recommended_compound="",
                tyre_life_remaining={},
            )

        planned_lap = next_stop["lap"]
        compound = next_stop["compound"]

        # Adjust window based on conditions
        early = strategy.pit_window_early
        late = strategy.pit_window_late

        # Tyre condition adjustment
        tyre_age = driver_state["tyre_age"]
        compound_obj = self._spec_for(driver_state["compound"])
        if tyre_age > _optimal_laps(compound_obj):
            early += 2  # Bring forward
            late = min(late, 2)

        # Safety car adjustment
        if safety_car_probability > 0.3:
            late += 3  # Extend window for SC opportunity

        # Fuel adjustment
        fuel_kg = driver_state.get("fuel_kg", 50)
        if fuel_kg < 10:
            early = max(early, 1)  # Must pit soon

        earliest = max(current_lap + 1, planned_lap - early)
        latest = min(current_lap + laps_remaining, planned_lap + late)

        # Optimal lap: balance tyre life vs track position
        optimal = planned_lap
        if tyre_age > _optimal_laps(compound_obj):
            optimal = earliest
        elif safety_car_probability > 0.25:
            optimal = latest  # Wait for potential SC

        # Available compounds
        used = set()
        # Would need race history to track used compounds
        available = [c for c in ["soft", "medium", "hard"] if c != driver_state["compound"]]

        # Tyre life remaining
        tyre_life = {}
        for c_name, c_obj in self.compounds.items():
            if c_obj.compound_type in (CompoundType.SOFT, CompoundType.MEDIUM, CompoundType.HARD):
                key = getattr(c_name, "value", str(c_name)).lower()
                tyre_life[key] = max(0, _optimal_laps(c_obj) * 2 - tyre_age)

        return PitWindow(
            driver_id=driver_state["driver_id"],
            planned_lap=planned_lap,
            earliest_lap=earliest,
            latest_lap=latest,
            optimal_lap=optimal,
            reason="Scheduled stop" if next_stop.get("reason") == "scheduled" else "Strategy adjustment",  # noqa: E501
            compounds_available=available,
            recommended_compound=compound,
            tyre_life_remaining=tyre_life,
        )

    def make_pit_decision(
        self,
        driver_state: dict[str, Any],
        strategy: PitStopStrategy,
        competitors: list[dict[str, Any]],
        track_pit_lane_loss: float,
        laps_remaining: int,
        safety_car_active: bool = False,
        safety_car_probability: float = 0.1,
        weather_change_imminent: bool = False,
    ) -> PitStopDecision:
        """Make real-time pit stop decision."""
        current_lap = driver_state["current_lap"]
        next_stop = strategy.get_next_stop(current_lap)

        # Check reactive triggers
        if weather_change_imminent:
            return PitStopDecision(
                driver_id=driver_state["driver_id"],
                current_lap=current_lap,
                should_pit_now=True,
                should_pit_next_lap=False,
                trigger=PitStopTrigger.WEATHER_CHANGE,
                recommended_compound=self._recommend_wet_compound(driver_state),
                reason="Weather change imminent",
                confidence=0.95,
                alternative_options=[],
            )

        if safety_car_active and strategy.reactive_to_safety_car:
            # Pit under SC if within window or tyres worn
            window = self.calculate_pit_window(driver_state, strategy, track_pit_lane_loss, laps_remaining, safety_car_probability)  # noqa: E501
            if current_lap >= window.earliest_lap - 2:
                return PitStopDecision(
                    driver_id=driver_state["driver_id"],
                    current_lap=current_lap,
                    should_pit_now=True,
                    should_pit_next_lap=False,
                    trigger=PitStopTrigger.SAFETY_CAR,
                    recommended_compound=window.recommended_compound or driver_state["compound"],
                    reason="Safety car - free pit stop",
                    confidence=0.9,
                    alternative_options=[],
                )

        # Check scheduled stop window
        if next_stop:
            window = self.calculate_pit_window(driver_state, strategy, track_pit_lane_loss, laps_remaining, safety_car_probability)  # noqa: E501

            if current_lap >= window.optimal_lap:
                # Check undercut opportunities
                undercut = None
                for comp in competitors:
                    if comp["gap_ahead"] > 0 and comp["gap_ahead"] < strategy.undercut_threshold * 5:  # noqa: E501
                        uc = self.analyze_undercut(driver_state, comp, track_pit_lane_loss, laps_remaining)  # noqa: E501
                        if uc.is_viable:
                            undercut = uc
                            break

                # Check overcut opportunities
                overcut = None
                for comp in competitors:
                    if comp["gap_ahead"] < 0 and abs(comp["gap_ahead"]) < strategy.overcut_threshold * 5:  # noqa: E501
                        oc = self.analyze_overcut(driver_state, comp, track_pit_lane_loss, laps_remaining)  # noqa: E501
                        if oc.is_viable:
                            overcut = oc
                            break

                return PitStopDecision(
                    driver_id=driver_state["driver_id"],
                    current_lap=current_lap,
                    should_pit_now=True,
                    should_pit_next_lap=False,
                    trigger=PitStopTrigger.SCHEDULED,
                    recommended_compound=window.recommended_compound,
                    reason=f"Optimal pit window (lap {window.optimal_lap})",
                    confidence=0.85,
                    alternative_options=[
                        {"lap": window.earliest_lap, "reason": "Early stop for undercut", "score": 0.7},  # noqa: E501
                        {"lap": window.latest_lap, "reason": "Late stop for overcut", "score": 0.6},
                    ],
                    undercut_analysis=undercut,
                    overcut_analysis=overcut,
                )

            elif current_lap == window.optimal_lap - 1:
                return PitStopDecision(
                    driver_id=driver_state["driver_id"],
                    current_lap=current_lap,
                    should_pit_now=False,
                    should_pit_next_lap=True,
                    trigger=PitStopTrigger.SCHEDULED,
                    recommended_compound=window.recommended_compound,
                    reason=f"Pit next lap (optimal window: {window.optimal_lap})",
                    confidence=0.8,
                    alternative_options=[],
                )

        # Default: stay out
        return PitStopDecision(
            driver_id=driver_state["driver_id"],
            current_lap=current_lap,
            should_pit_now=False,
            should_pit_next_lap=False,
            trigger=PitStopTrigger.SCHEDULED,
            recommended_compound=driver_state["compound"],
            reason="Stay out - outside pit window",
            confidence=0.7,
            alternative_options=[],
        )

    def _recommend_wet_compound(self, driver_state: dict[str, Any]) -> str:
        """Recommend wet compound based on conditions."""
        # Simplified - would need weather intensity
        return "intermediate"


class PitStopSimulator:
    """Simulates pit stop execution with variability."""

    def __init__(self, pit_stop_model: PitStopModel | None = None):
        self.model = pit_stop_model or DEFAULT_PIT_STOP_MODEL
        self.rng = np.random.default_rng()

    def simulate_stop(
        self,
        driver_id: str,
        lap: int,
        compound: str,
        team_pit_skill: float,
        track_pit_lane_loss: float,
        old_compound: str = "",
        old_tyre_age: int = 0,
    ) -> PitStopEvent:
        """Simulate a complete pit stop."""
        team_factor = 1.1 - (team_pit_skill / 100) * 0.15

        total_loss, details = self.model.calculate_stop_time(compound, team_factor, self.rng)

        event = PitStopEvent(
            driver_id=driver_id,
            lap=lap,
            stop_type=PitStopType.PLANNED,
            pit_entry_time=0,  # Would be set by race sim
            pit_exit_time=total_loss,
            stationary_time=details["stationary_time"],
            total_time_loss=total_loss,
            old_compound=old_compound,
            new_compound=compound,
            old_tyre_age=old_tyre_age,
            was_planned=True,
            trigger_reason="scheduled",
        )

        if details["issue"]:
            event.had_issue = True
            event.issue_type = details["issue"]
            event.issue_time_loss = details["issue_delay"]

        return event

    def simulate_stop_with_issue(
        self,
        driver_id: str,
        lap: int,
        compound: str,
        team_pit_skill: float,
        track_pit_lane_loss: float,
        issue_type: str,
    ) -> PitStopEvent:
        """Simulate pit stop with specific issue."""
        event = self.simulate_stop(driver_id, lap, compound, team_pit_skill, track_pit_lane_loss)
        event.had_issue = True
        event.issue_type = issue_type
        event.stop_type = PitStopType.EMERGENCY
        return event
