from __future__ import annotations

import numpy as np

from app.simulation.environment.models import OvertakeZone  # noqa: F401
from app.simulation.racing.models import (
    BattleConfig,
    BattleContext,
    BattleDecision,
    BattleState,
    BattleStateType,
    DefenseMode,
    BattleResourceState,
    OvertakeContext,
)
from app.simulation.racing.overtake import OvertakeEngine


class BattleEngine:
    """Manages persistent battles between drivers."""

    def __init__(
        self,
        config: BattleConfig | None = None,
        overtake_engine: OvertakeEngine | None = None,
    ):
        self.config = config or BattleConfig()
        self.overtake_engine = overtake_engine or OvertakeEngine()
        self._active_battles: dict[tuple[str, str], BattleState] = {}

    def update_battle(
        self,
        context: BattleContext,
        rng: np.random.Generator,
    ) -> BattleDecision:
        """Update or create a battle state."""
        # Get or create battle state
        battle_key = (context.attacker_id, context.defender_id)

        if battle_key not in self._active_battles:
            # Check if battle should be created
            if context.gap > self.config.battle_creation_gap and not context.drs_state:
                return BattleDecision(
                    new_state=BattleStateType.NO_BATTLE,
                    overtake_probability=0.0,
                    defense_mode=DefenseMode.NORMAL,
                    incident_risk_multiplier=1.0,
                    debug_info={"reason": "gap_too_large_for_battle"},
                )

            # Create new battle
            battle = BattleState(
                attacker_id=context.attacker_id,
                defender_id=context.defender_id,
                state=BattleStateType.CLOSING,
                created_lap=context.current_lap,
                last_update_lap=context.current_lap,
            )
            self._active_battles[battle_key] = battle
        else:
            battle = self._active_battles[battle_key]

        # Update battle state
        battle.laps_active += 1
        battle.last_update_lap = context.current_lap
        battle.gap = context.gap
        battle.min_gap = min(battle.min_gap, context.gap)
        battle.max_gap = max(battle.max_gap, context.gap)

        if context.drs_state:
            battle.drs_available_laps += 1

        # Check for battle termination
        if (context.gap > self.config.battle_termination_gap or
            battle.laps_active > self.config.max_battle_laps):
            # Battle ends
            del self._active_battles[battle_key]
            return BattleDecision(
                new_state=BattleStateType.BATTLE_ENDED,
                overtake_probability=0.0,
                defense_mode=DefenseMode.NORMAL,
                incident_risk_multiplier=1.0,
                debug_info={"reason": "battle_terminated", "laps": battle.laps_active},
            )

        # Determine state transition
        new_state = self._determine_state_transition(battle, context)
        battle.state = new_state

        # Calculate overtake probability using overtake engine
        overtake_ctx = self._build_overtake_context(context)
        overtake_decision = self.overtake_engine.evaluate_opportunity(overtake_ctx, rng)

        # Adjust probability based on battle state and resource state
        adjusted_prob = self._adjust_probability_for_battle(
            overtake_decision.probability, battle, new_state, context
        )

        # Determine defense mode (fuel/ERS aware)
        defense_mode = self._determine_defense_mode(battle, context)

        # Calculate incident risk
        incident_risk = self._calculate_incident_risk(
            battle, context, defense_mode, new_state
        )

        debug_info = {
            "battle_laps": battle.laps_active,
            "min_gap": battle.min_gap,
            "max_gap": battle.max_gap,
            "attack_attempts": battle.attack_attempts,
            "state": new_state.value,
            "base_probability": overtake_decision.probability,
            "adjusted_probability": adjusted_prob,
        }

        return BattleDecision(
            new_state=new_state,
            overtake_probability=adjusted_prob,
            defense_mode=defense_mode,
            incident_risk_multiplier=incident_risk,
            debug_info=debug_info,
        )

    def _determine_state_transition(
        self,
        battle: BattleState,
        context: BattleContext,
    ) -> BattleStateType:
        """Determine the new battle state based on context."""
        current = battle.state

        if current == BattleStateType.NO_BATTLE:
            return BattleStateType.CLOSING

        elif current == BattleStateType.CLOSING:
            if context.gap <= self.config.closing_to_attacking_gap:
                return BattleStateType.ATTACKING
            elif context.drs_state:
                return BattleStateType.WITHIN_DRS
            else:
                return BattleStateType.CLOSING

        elif current == BattleStateType.WITHIN_DRS:
            if context.gap <= self.config.closing_to_attacking_gap:
                return BattleStateType.ATTACKING
            elif context.gap > self.config.battle_drs_gap:
                return BattleStateType.CLOSING
            else:
                return BattleStateType.WITHIN_DRS

        elif current == BattleStateType.ATTACKING:
            if context.gap <= self.config.attacking_to_side_by_side_gap:
                return BattleStateType.SIDE_BY_SIDE
            elif context.gap > self.config.closing_to_attacking_gap + 0.2:
                return BattleStateType.CLOSING
            else:
                return BattleStateType.ATTACKING

        elif current == BattleStateType.SIDE_BY_SIDE:
            battle.side_by_side_laps += 1
            if battle.side_by_side_laps >= self.config.side_by_side_timeout_laps:
                # Battle resolves - either overtake or fall back
                return BattleStateType.BATTLE_ENDED
            else:
                return BattleStateType.SIDE_BY_SIDE

        elif current == BattleStateType.DEFENDING:
            if context.gap > self.config.closing_to_attacking_gap + 0.2:
                return BattleStateType.CLOSING
            else:
                return BattleStateType.DEFENDING

        return current

    def _adjust_probability_for_battle(
        self,
        base_prob: float,
        battle: BattleState,
        state: BattleStateType,
        context: BattleContext,
    ) -> float:
        """Adjust overtake probability based on battle state and resource state."""
        prob = base_prob

        if state == BattleStateType.SIDE_BY_SIDE:
            prob += self.config.side_by_side_overtake_bonus
        elif state == BattleStateType.WITHIN_DRS:
            prob *= self.config.drs_effectiveness_in_battle

        # Experience factor - longer battles slightly favor defender
        if battle.laps_active > 5:
            prob *= 0.95

        # Fuel/ERS resource adjustment
        if context.attacker_resource_state:
            # Attacker with low fuel/ERS less likely to succeed
            if context.attacker_resource_state.fuel_conservation_required:
                prob *= 0.85
            if context.attacker_resource_state.ers_conservation_required:
                prob *= 0.9
            # Attacker with good resources more likely to attack
            if context.attacker_resource_state.can_attack:
                prob *= 1.05

        if context.defender_resource_state:
            # Defender with low resources more vulnerable
            if context.defender_resource_state.fuel_conservation_required:
                prob *= 1.1
            if context.defender_resource_state.ers_conservation_required:
                prob *= 1.05

        # Experience factor - longer battles slightly favor defender
        if battle.laps_active > 5:
            prob *= 0.95

        return min(prob, 0.9)

    def _determine_defense_mode(
        self,
        battle: BattleState,
        context: BattleContext,
    ) -> DefenseMode:
        """Determine defender's defense mode (fuel/ERS aware)."""
        relative_pace = context.relative_pace  # negative = attacker faster

        # Get base thresholds
        aggressive_threshold = self.config.aggressive_defense_threshold
        defensive_threshold = self.config.defensive_defense_threshold

        # Adjust thresholds based on defender's resource state
        if context.defender_resource_state:
            # Defender with low fuel/ERS defends less aggressively
            if context.defender_resource_state.fuel_conservation_required:
                aggressive_threshold += 0.1
                defensive_threshold += 0.05
            if context.defender_resource_state.ers_conservation_required:
                aggressive_threshold += 0.1
                defensive_threshold += 0.05
            # Defender with good resources defends more aggressively
            if not context.defender_resource_state.fuel_conservation_required and \
               not context.defender_resource_state.ers_conservation_required:
                aggressive_threshold -= 0.05
                defensive_threshold -= 0.02

        if relative_pace < aggressive_threshold:
            return DefenseMode.AGGRESSIVE
        elif relative_pace < defensive_threshold:
            return DefenseMode.DEFENSIVE
        else:
            return DefenseMode.NORMAL

    def _calculate_incident_risk(
        self,
        battle: BattleState,
        context: BattleContext,
        defense_mode: DefenseMode,
        state: BattleStateType,
    ) -> float:
        """Calculate incident risk multiplier (fuel/ERS aware)."""
        risk = 1.0

        # Base risk from battle
        risk += battle.laps_active * 0.02

        # Defense mode
        if defense_mode == DefenseMode.DEFENSIVE:
            risk *= 1.3
        elif defense_mode == DefenseMode.AGGRESSIVE:
            risk *= 2.0

        # State
        if state == BattleStateType.SIDE_BY_SIDE:
            risk *= self.config.side_by_side_incident_multiplier

        # Aggression
        risk *= (1.0 + context.attacker_aggression / 100 * 0.5)
        risk *= (1.0 + context.defender_aggression / 100 * 0.3)

        # Weather
        if context.weather in ("light_rain", "heavy_rain"):
            risk *= 1.5
        elif context.weather in ("damp", "wet"):
            risk *= 1.2

        # Fuel/ERS resource effects on incident risk
        if context.attacker_resource_state:
            if context.attacker_resource_state.fuel_conservation_required:
                risk *= 1.1
            if context.attacker_resource_state.ers_conservation_required:
                risk *= 1.05

        if context.defender_resource_state:
            if context.defender_resource_state.fuel_conservation_required:
                risk *= 1.15
            if context.defender_resource_state.ers_conservation_required:
                risk *= 1.1

        return min(risk, 5.0)  # Cap at 5x

    def _build_overtake_context(self, context: BattleContext) -> OvertakeContext:
        """Build OvertakeContext from BattleContext."""
        # Map ERS mode to string
        ers_map = {
            "overtake": "overtake",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }

        # Determine corner type (simplified - would be sector-based in reality)
        corner_type = "medium"  # Default
        if context.overtake_zone:
            corner_type = context.overtake_zone.corner_type

        # Build resource states for overtake context
        attacker_resource_state = None
        defender_resource_state = None

        if context.attacker_resource_state:
            attacker_resource_state = context.attacker_resource_state

        if context.defender_resource_state:
            defender_resource_state = context.defender_resource_state

        return OvertakeContext(
            attacker_id=context.attacker_id,
            defender_id=context.defender_id,
            attacker_position=0,  # Not needed for probability
            defender_position=0,
            gap=context.gap,
            relative_pace=context.relative_pace,
            attacker_tyre_compound="medium",  # Would be passed in real use
            defender_tyre_compound="medium",
            attacker_tyre_age=0,
            defender_tyre_age=0,
            tyre_delta=context.tyre_delta,
            attacker_ers_mode=ers_map.get(context.attacker_ers_mode, "medium"),
            defender_ers_mode=ers_map.get(context.defender_ers_mode, "medium"),
            drs_available=context.drs_state,
            attacker_straight_line_advantage=0.0,
            defender_defensive_skill=context.defender_defensive_skill,
            attacker_overtaking_skill=context.attacker_overtaking_skill,
            attacker_aggression=context.attacker_aggression,
            track_overtaking_difficulty=context.track_overtaking_difficulty,
            corner_type=corner_type,
            dirty_air_effect=context.dirty_air,
            weather=context.weather,
            track_wetness=context.track_wetness,
            attacker_damage=context.attacker_damage,
            defender_damage=context.defender_damage,
            safety_car_active=context.safety_car_active,
            vsc_active=context.vsc_active,
            traffic_ahead=False,

            # Phase 7 additions
            attacker_resource_state=attacker_resource_state,
            defender_resource_state=defender_resource_state,
            overtake_zone=context.overtake_zone,
            sector=context.sector,
            forecast=context.forecast,
            track_wetness_racing_line=context.track_wetness_racing_line,
            track_wetness_off_line=context.track_wetness_off_line,
            drying_line_active=context.drying_line_active,
            attacker_ers_energy=context.attacker_ers_energy if hasattr(context, 'attacker_ers_energy') else 1.0,  # noqa: E501
            defender_ers_energy=context.defender_ers_energy if hasattr(context, 'defender_ers_energy') else 1.0,  # noqa: E501
        )

    def record_attack_attempt(self, attacker_id: str, defender_id: str, success: bool) -> None:
        """Record an attack attempt."""
        battle_key = (attacker_id, defender_id)
        if battle_key in self._active_battles:
            battle = self._active_battles[battle_key]
            battle.attack_attempts += 1
            if success:
                battle.successful_overtakes += 1
                # Battle ends on successful overtake
                del self._active_battles[battle_key]

    def record_incident(self, attacker_id: str, defender_id: str) -> None:
        """Record an incident in battle."""
        battle_key = (attacker_id, defender_id)
        if battle_key in self._active_battles:
            battle = self._active_battles[battle_key]
            battle.incidents += 1

    def get_battle(self, attacker_id: str, defender_id: str) -> BattleState | None:
        """Get battle state if exists."""
        return self._active_battles.get((attacker_id, defender_id))

    def get_all_battles(self) -> dict[tuple[str, str], BattleState]:
        """Get all active battles."""
        return self._active_battles.copy()

    def clear_battle(self, attacker_id: str, defender_id: str) -> None:
        """Manually clear a battle."""
        battle_key = (attacker_id, defender_id)
        if battle_key in self._active_battles:
            del self._active_battles[battle_key]

    def reset(self) -> None:
        """Clear all active battles (call at race start for isolation)."""
        self._active_battles.clear()
