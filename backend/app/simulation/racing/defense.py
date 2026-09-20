from __future__ import annotations

from typing import Any

import numpy as np

from app.simulation.racing.models import (
    DefenseConfig,
    DefenseContext,
    DefenseDecision,
    DefenseMode,
)


class DefenseModel:
    """Determines defensive driving behavior (predictive model)."""

    def __init__(
        self,
        config: DefenseConfig | None = None,
    ):
        self.config = config or DefenseConfig()

    def evaluate_defense(
        self,
        context: DefenseContext,
        rng: np.random.Generator,
    ) -> DefenseDecision:
        """Evaluate defensive driving decision (predictive)."""

        # Predict attack probability
        attack_probability = self._predict_attack_probability(context)

        # Determine defense mode based on predicted attack
        mode = self._determine_mode(context, attack_probability)

        # Choose racing line
        line_choice = self._choose_line(context, mode, rng)

        # Calculate pace cost
        pace_cost = self._calculate_pace_cost(mode, context)

        # Calculate incident risk multiplier
        incident_risk = self._calculate_incident_risk(mode, context)

        debug_info = {
            "relative_pace": context.relative_pace,
            "defender_skill": context.defender_defensive_skill,
            "defender_aggression": context.defender_aggression,
            "defender_pressure_resistance": context.defender_pressure_resistance,
            "defender_tyre_condition": context.defender_tyre_condition,
            "attacker_skill": context.attacker_overtaking_skill,
            "track_difficulty": context.track_overtaking_difficulty,
            "laps_remaining": context.laps_remaining,
            "position": context.position,
            "mode": mode.value,
            "line_choice": line_choice,
            "predicted_attack_probability": attack_probability,
        }

        return DefenseDecision(
            mode=mode,
            line_choice=line_choice,
            incident_risk_multiplier=incident_risk,
            pace_cost=pace_cost,
            debug_info=debug_info,
        )

    def _predict_attack_probability(self, context: DefenseContext) -> float:
        """Predict probability of attack based on context."""
        probability = 0.5  # Base probability

        # Relative pace (attacker faster = higher probability)
        if context.relative_pace < 0:
            probability += (-context.relative_pace) * 0.5

        # Tyre advantage
        if context.attacker_tyre_condition > context.defender_tyre_condition:
            probability += (context.attacker_tyre_condition - context.defender_tyre_condition) * 0.3

        # DRS available
        if context.overtake_zone and context.overtake_zone.drs_available:
            probability += 0.2

        # Attacker skill
        probability += (context.attacker_overtaking_skill - 50) * 0.01

        # Defender tyre condition
        if context.defender_tyre_condition < 0.5:
            probability += 0.1

        # Gap (closer = higher probability)
        if context.gap < 1.0:
            probability += (1.0 - context.gap) * 0.3

        # Weather
        if context.weather in ("light_rain", "heavy_rain"):
            probability *= 0.7  # Less overtaking in wet
        elif context.weather in ("damp", "wet"):
            probability *= 0.85

        # Fuel/ERS resource state
        if context.attacker_resource_state:
            if not context.attacker_resource_state.fuel_conservation_required and \
               not context.attacker_resource_state.ers_conservation_required:
                # Attacker has resources to attack
                probability += 0.1
            if context.attacker_resource_state.fuel_conservation_required:
                probability *= 0.8  # Less likely to attack if saving fuel
            if context.attacker_resource_state.ers_conservation_required:
                probability *= 0.9  # Less likely to attack if saving ERS

        if context.defender_resource_state:
            if context.defender_resource_state.fuel_conservation_required:
                probability += 0.1  # Defender saving fuel = easier to attack
            if context.defender_resource_state.ers_conservation_required:
                probability *= 1.1  # Defender saving ERS = harder to defend

        # Track difficulty
        probability *= (1.0 - context.track_overtaking_difficulty * 0.5)

        # Laps remaining - more attacks later
        if context.laps_remaining < 10:
            probability += 0.1

        return max(0.0, min(1.0, probability))

    def _determine_mode(self, context: DefenseContext, attack_probability: float) -> DefenseMode:
        """Determine defense mode based on predicted attack probability."""

        relative_pace = context.relative_pace  # negative = attacker faster

        # Base thresholds
        aggressive_threshold = self.config.aggressive_defense_threshold
        defensive_threshold = self.config.defensive_defense_threshold
        normal_threshold = self.config.normal_defense_threshold

        # Adjust thresholds based on driver characteristics
        skill_adj = (context.defender_defensive_skill - 50) * self.config.defensive_skill_coeff
        pressure_adj = (context.defender_pressure_resistance - 50) * self.config.pressure_resistance_coeff  # noqa: E501

        # Aggressive drivers defend more aggressively
        aggression_adj = (context.defender_aggression - 50) * 0.005

        # Adjust thresholds
        aggressive_threshold += skill_adj + pressure_adj + aggression_adj
        defensive_threshold += skill_adj * 0.5 + pressure_adj * 0.5 + aggression_adj * 0.5
        normal_threshold += skill_adj * 0.2

        # Tyre condition - worn tyres reduce aggressive defense
        if context.defender_tyre_condition > self.config.worn_tyre_aggressive_threshold:
            aggressive_threshold -= 0.3  # Harder to defend aggressively

        # Track difficulty - harder tracks encourage more defense
        track_adj = (context.track_overtaking_difficulty - 0.5) * 0.2
        aggressive_threshold += track_adj
        defensive_threshold += track_adj * 0.5

        # Laps remaining - more defense later in race
        if context.laps_remaining < 10:
            aggressive_threshold += 0.1
            defensive_threshold += 0.05

        # Attack probability adjustment
        if attack_probability > 0.7:
            aggressive_threshold -= 0.2
            defensive_threshold -= 0.1
        elif attack_probability > 0.5:
            aggressive_threshold -= 0.1

        # Fuel/ERS resource adjustments
        if context.defender_resource_state:
            if context.defender_resource_state.fuel_conservation_required:
                aggressive_threshold += 0.15
                defensive_threshold += 0.05
            if context.defender_resource_state.ers_conservation_required:
                aggressive_threshold += 0.1
                defensive_threshold += 0.05

        if context.attacker_resource_state:
            if context.attacker_resource_state.fuel_conservation_required:
                aggressive_threshold += 0.1
                defensive_threshold += 0.05
            if context.attacker_resource_state.ers_conservation_required:
                aggressive_threshold += 0.05

        # Team orders
        if context.is_teammate:
            if context.team_order == "hold":
                aggressive_threshold += 0.2
                defensive_threshold += 0.1
            elif context.team_order == "let_by":
                aggressive_threshold += 0.3
                defensive_threshold += 0.2

        # Determine mode
        if relative_pace <= aggressive_threshold:
            return DefenseMode.AGGRESSIVE
        elif relative_pace <= defensive_threshold:
            return DefenseMode.DEFENSIVE
        else:
            return DefenseMode.NORMAL

    def _choose_line(
        self,
        context: DefenseContext,
        mode: DefenseMode,
        rng: np.random.Generator,
    ) -> str:
        """Choose defensive racing line."""

        # Corner type influences line choice
        if context.corner_type in ("hairpin", "slow", "chicane"):
            # Tight corners - inside line preferred for defense
            inside_prob = 0.7
        elif context.corner_type in ("medium", "double_apex"):
            inside_prob = 0.6
        else:  # fast, high_speed
            inside_prob = 0.4  # Outside can be better for exit speed

        # Mode influences line choice
        if mode == DefenseMode.AGGRESSIVE:
            inside_prob += 0.15
        elif mode == DefenseMode.DEFENSIVE:
            inside_prob += 0.05

        # Attacker skill - better overtakers force more inside defense
        if context.attacker_overtaking_skill > 80:
            inside_prob += 0.1

        # Weather - wet conditions favor inside (drier line)
        if context.weather in ("light_rain", "heavy_rain", "damp", "wet"):
            inside_prob += 0.1

        # Overtake zone adjustment
        if context.overtake_zone:
            # Zone with high straight-line importance = more inside defense
            inside_prob += context.overtake_zone.straight_line_importance * 0.1

        inside_prob = min(max(inside_prob, 0.2), 0.9)

        if rng.random() < inside_prob:
            return "inside"
        else:
            return "outside"

    def _calculate_pace_cost(
        self,
        mode: DefenseMode,
        context: DefenseContext,
    ) -> float:
        """Calculate pace cost of defending (sec/lap)."""

        base_cost = {
            DefenseMode.NORMAL: self.config.normal_pace_cost,
            DefenseMode.DEFENSIVE: self.config.defensive_pace_cost,
            DefenseMode.AGGRESSIVE: self.config.aggressive_pace_cost,
        }[mode]

        # Adjust for corner type
        if context.corner_type in ("hairpin", "slow", "chicane"):
            base_cost *= 1.2
        elif context.corner_type in ("fast", "high_speed"):
            base_cost *= 0.7

        # Adjust for skill - better defenders lose less pace
        skill_factor = 1.0 - (context.defender_defensive_skill - 50) * 0.005
        skill_factor = max(skill_factor, 0.5)

        # Adjust for fuel/ERS conservation
        if context.defender_resource_state:
            if context.defender_resource_state.fuel_conservation_required:
                base_cost *= 0.8  # Saving fuel = slower anyway
            if context.defender_resource_state.ers_conservation_required:
                base_cost *= 0.9

        # Adjust for skill - better defenders lose less pace
        skill_factor = 1.0 - (context.defender_defensive_skill - 50) * 0.005
        skill_factor = max(skill_factor, 0.5)

        return base_cost * skill_factor

    def _calculate_incident_risk(
        self,
        mode: DefenseMode,
        context: DefenseContext,
    ) -> float:
        """Calculate incident risk multiplier."""

        base_risk = {
            DefenseMode.NORMAL: self.config.normal_risk,
            DefenseMode.DEFENSIVE: self.config.defensive_risk,
            DefenseMode.AGGRESSIVE: self.config.aggressive_risk,
        }[mode]

        # Attacker aggression increases risk
        attacker_risk = 1.0 + context.attacker_aggression / 100 * 0.5

        # Worn tyres increase risk
        tyre_risk = 1.0 + context.defender_tyre_condition * 0.5

        # Weather
        weather_risk = 1.0
        if context.weather in ("light_rain", "heavy_rain"):
            weather_risk = 2.0
        elif context.weather in ("damp", "wet"):
            weather_risk = 1.3

        # Fuel/ERS resource effects on incident risk
        if context.defender_resource_state:
            if context.defender_resource_state.fuel_conservation_required:
                base_risk *= 1.1
            if context.defender_resource_state.ers_conservation_required:
                base_risk *= 1.05

        return base_risk * attacker_risk * tyre_risk * weather_risk

    def get_debug_info(self, context: DefenseContext) -> dict[str, Any]:
        """Get detailed debug information."""
        decision = self.evaluate_defense(context, np.random.default_rng(0))
        return {
            "mode": decision.mode.value,
            "line_choice": decision.line_choice,
            "pace_cost": decision.pace_cost,
            "incident_risk_multiplier": decision.incident_risk_multiplier,
            "thresholds": {
                "aggressive": self.config.aggressive_defense_threshold,
                "defensive": self.config.defensive_defense_threshold,
                "normal": self.config.normal_defense_threshold,
            },
            "context": {
                "relative_pace": context.relative_pace,
                "defender_skill": context.defender_defensive_skill,
                "defender_aggression": context.defender_aggression,
                "defender_tyre": context.defender_tyre_condition,
                "attacker_skill": context.attacker_overtaking_skill,
                "track_difficulty": context.track_overtaking_difficulty,
            },
        }
