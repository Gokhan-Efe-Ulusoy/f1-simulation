from __future__ import annotations

from typing import Any

import numpy as np

from app.simulation.racing.models import (
    OvertakeConfig,
    OvertakeContext,
    OvertakeDecision,
    OvertakePhase,
)


class OvertakeEngine:
    """Evaluates overtake opportunities and attempts."""

    def __init__(
        self,
        config: OvertakeConfig | None = None,
    ):
        self.config = config or OvertakeConfig()

    def evaluate_opportunity(
        self,
        context: OvertakeContext,
        rng: np.random.Generator,
    ) -> OvertakeDecision:
        """Evaluate whether an overtake opportunity exists and its probability."""

        # Check basic opportunity conditions
        if context.safety_car_active or context.vsc_active:
            return OvertakeDecision(
                opportunity_exists=False,
                phase=OvertakePhase.NO_OPPORTUNITY,
                probability=0.0,
                factors={},
                recommended_action="back_off",
                debug_info={"reason": "safety_car_or_vsc"},
            )

        if context.gap > self.config.base_opportunity_gap:
            return OvertakeDecision(
                opportunity_exists=False,
                phase=OvertakePhase.NO_OPPORTUNITY,
                probability=0.0,
                factors={"gap": context.gap},
                recommended_action="wait",
                debug_info={"reason": "gap_too_large", "gap": context.gap},
            )

        # Determine phase based on gap
        if context.gap > self.config.attack_range_gap:
            phase = OvertakePhase.CLOSING
        elif context.gap > 0.2:
            phase = OvertakePhase.WITHIN_ATTACK_RANGE
        else:
            phase = OvertakePhase.OVERTAKE_OPPORTUNITY

        # Get overtake zone for current sector
        overtake_zone = context.overtake_zone

        # Calculate probability factors
        factors = {}

        # 1. Pace advantage (negative relative_pace = attacker faster)
        pace_advantage = -context.relative_pace
        if pace_advantage > 0:
            factors["pace_advantage"] = pace_advantage * self.config.pace_advantage_coeff
        else:
            factors["pace_advantage"] = pace_advantage * self.config.pace_advantage_coeff * 0.5

        # 2. Tyre advantage
        factors["tyre_delta"] = context.tyre_delta * self.config.tyre_delta_coeff

        # 3. Straight line advantage (enhanced by zone)
        straight_line_adv = context.attacker_straight_line_advantage
        if overtake_zone:
            straight_line_adv *= overtake_zone.straight_line_importance
        factors["straight_line"] = straight_line_adv * self.config.straight_line_coeff

        # 4. Driver skills
        factors["overtaking_skill"] = (context.attacker_overtaking_skill - 50) * self.config.overtaking_skill_coeff  # noqa: E501
        factors["defending_skill"] = (context.defender_defensive_skill - 50) * self.config.defending_skill_coeff  # noqa: E501
        factors["aggression"] = (context.attacker_aggression - 50) * self.config.aggression_coeff

        # 5. Track/sector difficulty
        track_difficulty = context.track_overtaking_difficulty
        if overtake_zone:
            track_difficulty = overtake_zone.overtake_difficulty / 100.0
        factors["track_difficulty"] = track_difficulty * self.config.track_difficulty_coeff

        # 6. Corner type (use zone corner type if available)
        corner_type = context.corner_type
        if overtake_zone:
            corner_type = overtake_zone.corner_type
        corner_mod = self.config.corner_type_modifiers.get(corner_type, 0.0)
        factors["corner_type"] = corner_mod

        # 7. DRS (enhanced by zone)
        drs_bonus = 0.0
        if context.drs_available:
            drs_bonus = self.config.drs_enabled_bonus
            if overtake_zone and overtake_zone.drs_available:
                drs_bonus *= overtake_zone.straight_line_importance
        factors["drs"] = drs_bonus

        # 8. ERS (enhanced by zone and ERS energy)
        ers_bonus = 0.0
        if context.attacker_ers_mode == "overtake":
            ers_bonus = self.config.ers_overtake_bonus
        elif context.attacker_ers_mode == "high":
            ers_bonus = self.config.ers_high_bonus

        # Adjust for ERS energy
        ers_energy = getattr(context, 'attacker_ers_energy', 1.0)
        ers_bonus *= ers_energy

        # Zone adjustment for ERS
        if overtake_zone:
            ers_bonus *= (1.0 + overtake_zone.straight_line_importance * 0.5)

        factors["ers"] = ers_bonus

        # 9. Dirty air (reduces following performance)
        factors["dirty_air"] = -context.dirty_air_effect * 1.5

        # 10. Weather
        if context.weather in ("light_rain", "heavy_rain"):
            factors["weather"] = self.config.wet_penalty
        elif context.weather in ("damp", "wet"):
            factors["weather"] = self.config.damp_penalty
        else:
            factors["weather"] = 0.0

        # 11. Damage
        factors["attacker_damage"] = -context.attacker_damage * self.config.damage_penalty
        factors["defender_damage"] = -context.defender_damage * self.config.damage_penalty * 0.5

        # 12. Traffic ahead
        if context.traffic_ahead:
            factors["traffic"] = self.config.traffic_penalty
        else:
            factors["traffic"] = 0.0

        # 13. Sector-specific overtaking opportunity
        if overtake_zone:
            factors["zone_opportunity"] = overtake_zone.get_overtake_difficulty_for_car(
                context.attacker_straight_line_advantage * 100 + 75,
                75,
                75
            ) / 100.0 * 0.1

        # 14. ERS energy advantage
        attacker_ers = getattr(context, 'attacker_ers_energy', 1.0)
        defender_ers = getattr(context, 'defender_ers_energy', 1.0)
        if attacker_ers > defender_ers:
            factors["ers_energy_advantage"] = (attacker_ers - defender_ers) * 0.2

        # 15. Drying line effect
        if context.drying_line_active:
            factors["drying_line"] = 0.05

        # Sum all factors and apply base probability
        logit = self.config.base_probability + sum(factors.values())

        # Convert logit to probability using sigmoid
        probability = 1.0 / (1.0 + np.exp(-logit))
        probability = min(max(probability, 0.0), self.config.max_probability)

        # Determine recommended action
        if probability > 0.6 and phase in (OvertakePhase.WITHIN_ATTACK_RANGE, OvertakePhase.OVERTAKE_OPPORTUNITY):  # noqa: E501
            recommended_action = "attack"
        elif probability > 0.3:
            recommended_action = "wait"
        else:
            recommended_action = "back_off"

        debug_info = {
            "gap": context.gap,
            "relative_pace": context.relative_pace,
            "tyre_delta": context.tyre_delta,
            "drs_available": context.drs_available,
            "logit": logit,
            "phase": phase.value,
            "overtake_zone": context.overtake_zone.name if context.overtake_zone else None,
            "sector": context.sector,
        }

        return OvertakeDecision(
            opportunity_exists=probability > 0.05,
            phase=phase,
            probability=probability,
            factors=factors,
            recommended_action=recommended_action,
            debug_info=debug_info,
        )

    def evaluate_attempt(
        self,
        context: OvertakeContext,
        rng: np.random.Generator,
    ) -> tuple[bool, str]:
        """Evaluate an overtake attempt result.

        Returns (success, reason).
        """
        decision = self.evaluate_opportunity(context, rng)

        if not decision.opportunity_exists:
            return False, "no_opportunity"

        # Roll for success
        roll = rng.random()
        success = roll < decision.probability

        if success:
            return True, "overtake_completed"
        else:
            # Check if incident
            incident_roll = rng.random()
            incident_risk = 0.05 + (1.0 - decision.probability) * 0.1
            if context.attacker_aggression > 80:
                incident_risk *= 1.5
            if context.weather in ("light_rain", "heavy_rain"):
                incident_risk *= 2.0

            if incident_roll < incident_risk:
                return False, "incident"
            else:
                return False, "defended"

    def get_debug_info(self, context: OvertakeContext) -> dict[str, Any]:
        """Get detailed debug information for an overtake context."""
        decision = self.evaluate_opportunity(context, np.random.default_rng(0))
        return {
            "context": {
                "attacker_id": context.attacker_id,
                "defender_id": context.defender_id,
                "gap": context.gap,
                "relative_pace": context.relative_pace,
                "tyre_delta": context.tyre_delta,
                "drs_available": context.drs_available,
                "attacker_ers_mode": context.attacker_ers_mode,
                "defender_ers_mode": context.defender_ers_mode,
                "corner_type": context.corner_type,
                "track_difficulty": context.track_overtaking_difficulty,
                "weather": context.weather,
            },
            "factors": decision.factors,
            "probability": decision.probability,
            "phase": decision.phase.value,
            "recommended_action": decision.recommended_action,
        }
