from __future__ import annotations

from typing import Any

import numpy as np

from app.simulation.racing.models import (
    SafetyCarRestartConfig,
    SafetyCarRestartContext,
    SafetyCarRestartResult,
)


class SafetyCarRestartModel:
    """Models safety car restart dynamics."""

    def __init__(
        self,
        config: SafetyCarRestartConfig | None = None,
    ):
        self.config = config or SafetyCarRestartConfig()

    def evaluate_restart(
        self,
        context: SafetyCarRestartContext,
        rng: np.random.Generator,
    ) -> SafetyCarRestartResult:
        """Evaluate safety car restart performance."""

        # Calculate reaction time
        reaction_time = self._calculate_reaction_time(context, rng)

        # Calculate acceleration advantage
        accel_advantage = self._calculate_acceleration_advantage(context, rng)

        # Calculate position change probabilities
        position_changes = self._calculate_position_changes(context, accel_advantage, rng)

        # Calculate incident risk
        incident_risk = self._calculate_incident_risk(context, rng)

        debug_info = {
            "reaction_time": reaction_time,
            "acceleration_advantage": accel_advantage,
            "start_performance": context.start_performance,
            "tyre_temp": context.tyre_temp,
            "tyre_age": context.tyre_age,
            "pressure_resistance": context.pressure_resistance,
            "aggression": context.aggression,
            "consistency": context.consistency,
            "laps_under_sc": context.laps_under_sc,
            "is_leader": context.is_leader,
        }

        return SafetyCarRestartResult(
            reaction_time=reaction_time,
            acceleration_advantage=accel_advantage,
            position_change_probability=position_changes,
            incident_risk=incident_risk,
            debug_info=debug_info,
        )

    def _calculate_reaction_time(
        self,
        context: SafetyCarRestartContext,
        rng: np.random.Generator,
    ) -> float:
        """Calculate driver reaction time at restart."""

        # Base reaction time (seconds)
        base_reaction = 0.3  # ~300ms base

        # Start performance skill effect
        skill_effect = (context.start_performance - 50) * self.config.start_skill_coeff

        # Pressure resistance
        pressure_effect = (context.pressure_resistance - 50) * self.config.start_skill_coeff * 0.5

        # Consistency - more consistent = more consistent reactions
        consistency_effect = (context.consistency - 50) * self.config.start_skill_coeff * 0.3

        # Aggression - aggressive drivers may react faster but with more variance
        aggression_effect = (context.aggression - 50) * self.config.start_skill_coeff * 0.3

        # Tyre temperature - cold tyres = slower reaction
        tyre_temp_effect = 0.0
        if context.tyre_temp < 80:
            tyre_temp_effect = (80 - context.tyre_temp) * self.config.tyre_temp_coeff

        # Tyre age - older tyres = slower
        tyre_age_effect = context.tyre_age * self.config.tyre_age_coeff

        # Weather
        weather_effect = 0.0
        if context.weather in ("light_rain", "heavy_rain"):
            weather_effect = 0.05  # Slower in wet
        elif context.weather in ("damp", "wet"):
            weather_effect = 0.02

        # Stochastic variation
        stochastic = rng.normal(0, self.config.reaction_variance)

        reaction = (base_reaction - skill_effect - pressure_effect -
                   consistency_effect - aggression_effect +
                   tyre_temp_effect + tyre_age_effect +
                   weather_effect + stochastic)

        # Clamp to reasonable range
        return max(0.1, min(1.0, reaction))

    def _calculate_acceleration_advantage(
        self,
        context: SafetyCarRestartContext,
        rng: np.random.Generator,
    ) -> float:
        """Calculate acceleration advantage relative to field average."""

        # Base advantage from start performance
        skill_adv = (context.start_performance - 50) * 0.01

        # Tyre temperature advantage
        temp_adv = (context.tyre_temp - 90) * self.config.tyre_temp_coeff * 2

        # Tyre age disadvantage
        age_disadv = context.tyre_age * self.config.tyre_age_coeff * 2

        # Pressure resistance
        pressure_adv = (context.pressure_resistance - 50) * 0.005

        # Stochastic
        stochastic = rng.normal(0, 0.05)

        advantage = skill_adv + temp_adv - age_disadv + pressure_adv + stochastic

        return max(-0.5, min(0.5, advantage))

    def _calculate_position_changes(
        self,
        context: SafetyCarRestartContext,
        accel_advantage: float,
        rng: np.random.Generator,
    ) -> dict[int, float]:
        """Calculate probabilities of position changes."""

        changes = {}

        # Base probabilities
        # Advantage > 0 means faster acceleration
        if accel_advantage > 0.1:
            # Good chance to gain position
            changes[1] = min(0.3 + accel_advantage * 0.5, 0.6)
            if accel_advantage > 0.25:
                changes[2] = min(0.1 + accel_advantage * 0.3, 0.25)
            changes[0] = 1.0 - sum(changes.values())
        elif accel_advantage < -0.1:
            # Chance to lose position
            changes[-1] = min(0.3 + abs(accel_advantage) * 0.5, 0.6)
            if accel_advantage < -0.25:
                changes[-2] = min(0.1 + abs(accel_advantage) * 0.3, 0.25)
                if accel_advantage < -0.4:
                    changes[-3] = 0.05
            changes[0] = 1.0 - sum(changes.values())
        else:
            # Neutral - mostly maintain position
            changes[0] = 0.85
            changes[1] = 0.08
            changes[-1] = 0.07

        # Adjust for position (leader can't gain, backmarkers can't lose many)
        if context.is_leader:
            # Leader can't gain
            gained = changes.get(1, 0) + changes.get(2, 0)
            changes[0] += gained
            changes[1] = 0.0
            changes[2] = 0.0
        elif context.position >= 18:
            # Backmarkers less likely to lose
            lost = changes.get(-1, 0) * 0.5 + changes.get(-2, 0) * 0.5
            changes[0] = changes.get(0, 0) + lost
            if -1 in changes:
                changes[-1] *= 0.5
            if -2 in changes:
                changes[-2] *= 0.5

        # Normalize
        total = sum(changes.values())
        if total > 0:
            changes = {k: v / total for k, v in changes.items()}

        return changes

    def _calculate_incident_risk(
        self,
        context: SafetyCarRestartContext,
        rng: np.random.Generator,
    ) -> float:
        """Calculate incident risk at restart."""

        risk = self.config.base_restart_incident_risk

        # Aggression increases risk
        risk += context.aggression * self.config.aggression_incident_coeff

        # Weather
        if context.weather in ("light_rain", "heavy_rain"):
            risk *= self.config.wet_incident_multiplier
        elif context.weather in ("damp", "wet"):
            risk *= self.config.wet_incident_multiplier * 0.6

        # Tyre condition
        if context.tyre_temp < 70:
            risk *= 1.5
        if context.tyre_age > 25:
            risk *= 1.3

        # Position - midfield more incidents
        if 5 <= context.position <= 15:
            risk *= 1.2

        return min(risk, 0.15)  # Cap at 15%

    def compress_field(
        self,
        driver_states: list[dict[str, Any]],
        rng: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """Compress field gaps under safety car."""

        if not driver_states:
            return driver_states

        # Sort by position
        sorted_drivers = sorted(driver_states, key=lambda d: d.get("position", 999))

        compressed = []
        for i, driver in enumerate(sorted_drivers):
            new_driver = driver.copy()

            if i == 0:
                # Leader
                new_driver["gap_ahead"] = 0.0
            else:
                # Compress gap with variance
                base_gap = self.config.target_gap_under_sc
                variance = rng.uniform(-self.config.gap_variance, self.config.gap_variance)
                new_driver["gap_ahead"] = max(0.1, base_gap + variance)

            compressed.append(new_driver)

        return compressed

    def get_debug_info(self, context: SafetyCarRestartContext) -> dict[str, Any]:
        """Get detailed debug information."""
        result = self.evaluate_restart(context, np.random.default_rng(0))
        return {
            "reaction_time": result.reaction_time,
            "acceleration_advantage": result.acceleration_advantage,
            "position_change_probs": result.position_change_probability,
            "incident_risk": result.incident_risk,
            "context": {
                "driver_id": context.driver_id,
                "position": context.position,
                "start_performance": context.start_performance,
                "tyre_temp": context.tyre_temp,
                "tyre_age": context.tyre_age,
                "pressure_resistance": context.pressure_resistance,
                "aggression": context.aggression,
                "consistency": context.consistency,
                "weather": context.weather,
                "is_leader": context.is_leader,
            },
        }
