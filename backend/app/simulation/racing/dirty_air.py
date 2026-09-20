from __future__ import annotations

from typing import Any

from app.simulation.racing.models import (
    DirtyAirConfig,
    DirtyAirContext,
    DirtyAirEffect,
)


class DirtyAirModel:
    """Models the aerodynamic penalty of following another car.

    This is a statistical/engineering approximation, NOT CFD.
    Uses smooth distance-dependent functions to avoid discontinuities.
    Supports sector-specific calculations.
    """

    def __init__(
        self,
        config: DirtyAirConfig | None = None,
    ):
        self.config = config or DirtyAirConfig()

    def calculate_effect(
        self,
        context: DirtyAirContext,
    ) -> DirtyAirEffect:
        """Calculate dirty air effect for a following car."""

        # Distance factor - smooth decay
        # At reference distance (1.0s), factor = 1.0
        # Closer = higher factor, further = lower factor
        distance_ratio = context.following_distance / self.config.reference_distance

        if distance_ratio <= 0:
            distance_ratio = 0.1  # Minimum

        # Smooth decay: factor = distance_ratio^(-exponent)
        # At 0.5s: factor ≈ 2.8x (for exponent=1.5)
        # At 1.0s: factor = 1.0x
        # At 2.0s: factor ≈ 0.35x
        # At 3.0s: factor ≈ 0.19x
        distance_factor = distance_ratio ** (-self.config.distance_exponent)

        # Cap the factor to prevent extreme values
        distance_factor = min(distance_factor, 5.0)

        # Aero sensitivity factor (0-100 scaled to ~0.5-2.0)
        aero_sens_factor = 0.5 + (context.follower_aero_sensitivity / 100) * self.config.aero_sensitivity_coeff * 100  # noqa: E501

        # Leader aero efficiency (more efficient = less wake)
        leader_eff_factor = 1.0 - (context.leader_aero_efficiency / 100) * self.config.aero_efficiency_coeff * 50  # noqa: E501
        leader_eff_factor = max(leader_eff_factor, 0.5)

        # Combined sensitivity factor
        sensitivity_factor = aero_sens_factor * leader_eff_factor

        # Sector-specific dirty air sensitivity
        sector_sensitivity = 1.0
        if hasattr(context, 'sector_dirty_air_sensitivity') and context.sector_dirty_air_sensitivity is not None:  # noqa: E501
            # Normalize to 50 = baseline
            sector_sensitivity = context.sector_dirty_air_sensitivity / 50.0

        # Corner type modifier
        corner_mod = self.config.corner_modifiers.get(context.corner_type, 1.0)

        # Weather modifier
        weather_mod = 1.0
        if context.weather in ("light_rain", "heavy_rain", "damp", "wet"):
            weather_mod = self.config.wet_reduction

        # Total factor
        total_factor = distance_factor * sensitivity_factor * sector_sensitivity * corner_mod * weather_mod  # noqa: E501

        # Calculate individual losses
        cornering_loss = self.config.base_cornering_loss * total_factor
        braking_loss = self.config.base_braking_loss * total_factor

        # Tyre temperature increase
        temp_increase = self.config.base_tyre_temp_increase * distance_factor * weather_mod

        # Degradation multiplier
        deg_multiplier = 1.0 + (self.config.base_degradation_multiplier - 1.0) * distance_factor * weather_mod  # noqa: E501

        # Total pace loss
        total_pace_loss = cornering_loss + braking_loss

        return DirtyAirEffect(
            cornering_loss=cornering_loss,
            braking_loss=braking_loss,
            tyre_temp_increase=temp_increase,
            degradation_multiplier=deg_multiplier,
            total_pace_loss=total_pace_loss,
        )

    def calculate_effect_for_sector(
        self,
        context: DirtyAirContext,
        sector: int,
        track: Any,
    ) -> DirtyAirEffect:
        """Calculate dirty air effect for a specific sector using track's sector sensitivity."""
        # Store sector sensitivity for calculation (normalized in calculate_effect)
        context.sector_dirty_air_sensitivity = track.get_sector_dirty_air_sensitivity(sector)

        return self.calculate_effect(context)

    def get_debug_info(self, context: DirtyAirContext) -> dict[str, Any]:
        """Get detailed debug information."""
        effect = self.calculate_effect(context)

        distance_ratio = context.following_distance / self.config.reference_distance
        distance_factor = distance_ratio ** (-self.config.distance_exponent) if distance_ratio > 0 else 5.0  # noqa: E501

        return {
            "following_distance": context.following_distance,
            "distance_ratio": distance_ratio,
            "distance_factor": distance_factor,
            "aero_sensitivity_factor": 0.5 + (context.follower_aero_sensitivity / 100) * self.config.aero_sensitivity_coeff * 100,  # noqa: E501
            "leader_efficiency_factor": max(1.0 - (context.leader_aero_efficiency / 100) * self.config.aero_efficiency_coeff * 50, 0.5),  # noqa: E501
            "corner_modifier": self.config.corner_modifiers.get(context.corner_type, 1.0),
            "weather_modifier": self.config.wet_reduction if context.weather in ("light_rain", "heavy_rain", "damp", "wet") else 1.0,  # noqa: E501
            "total_factor": distance_factor * (0.5 + (context.follower_aero_sensitivity / 100) * self.config.aero_sensitivity_coeff * 100) *  # noqa: E501
                           max(1.0 - (context.leader_aero_efficiency / 100) * self.config.aero_efficiency_coeff * 50, 0.5) *  # noqa: E501
                           self.config.corner_modifiers.get(context.corner_type, 1.0) *
                           (self.config.wet_reduction if context.weather in ("light_rain", "heavy_rain", "damp", "wet") else 1.0),  # noqa: E501
            "effects": {
                "cornering_loss": effect.cornering_loss,
                "braking_loss": effect.braking_loss,
                "tyre_temp_increase": effect.tyre_temp_increase,
                "degradation_multiplier": effect.degradation_multiplier,
                "total_pace_loss": effect.total_pace_loss,
            },
        }
