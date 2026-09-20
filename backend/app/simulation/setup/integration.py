"""Phase 20 — Setup integration with lap time model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.simulation.lap_time.model import LapTimeInputs, LapTimeModel, LapTimeComponents
from app.simulation.models.car import Car
from app.simulation.models.track import Track
from app.simulation.models.driver import Driver
from app.simulation.models.tyre import TyreCompound, TyreSpec
from app.simulation.models.weather import WeatherState
from app.simulation.setup.models import SetupState, SetupEffects, EvidenceTier
from app.simulation.setup.engine import SetupEngine, compute_setup_effects


@dataclass
class SetupLapTimeInputs:
    """Extended lap time inputs including setup."""
    base_inputs: LapTimeInputs
    setup: SetupState | None = None
    setup_effects: SetupEffects | None = None


class SetupAwareLapTimeModel(LapTimeModel):
    """LapTimeModel extended with setup effects integration."""

    # Setup sensitivity coefficients (PRIOR_ONLY unless calibrated)
    setup_downforce_sensitivity: float = 1.0
    setup_drag_sensitivity: float = 1.0
    setup_mechanical_sensitivity: float = 1.0
    setup_tyre_sensitivity: float = 1.0
    setup_evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY

    def calculate_lap_time_with_setup(
        self,
        inputs: LapTimeInputs,
        setup: SetupState | None = None,
        setup_effects: SetupEffects | None = None,
    ) -> LapTimeComponents:
        """Calculate lap time including setup effects."""
        # First compute base lap time via parent (avoid recursion through override)
        components = super().calculate_lap_time(inputs)

        # If no setup or no effects, return base
        if setup is None and setup_effects is None:
            return components

        # Compute setup effects if not provided
        if setup_effects is None and setup is not None:
            engine = SetupEngine(evidence_tier=self.setup_evidence_tier)
            setup_effects = engine.compute_effects(setup, inputs.car, inputs.track)

        if setup_effects is None:
            return components

        # Compute setup delta
        setup_delta = self._calculate_setup_delta(inputs, setup_effects)

        # Add setup delta to total
        total_time = components.total * (1.0 + setup_delta)

        # Apply minimum
        min_time = inputs.base_lap_time * self.min_lap_time_factor
        total_time = max(min_time, total_time)

        # Return components with setup delta added
        # Note: We modify the car_delta to include setup for backward compatibility
        # but track it separately in a new field
        return LapTimeComponents(
            base_time=components.base_time,
            car_delta=components.car_delta + setup_delta,
            driver_delta=components.driver_delta,
            fuel_delta=components.fuel_delta,
            tyre_delta=components.tyre_delta,
            tyre_degradation_delta=components.tyre_degradation_delta,
            weather_delta=components.weather_delta,
            traffic_delta=components.traffic_delta,
            track_evolution_delta=components.track_evolution_delta,
            drs_delta=components.drs_delta,
            ers_delta=components.ers_delta,
            damage_delta=components.damage_delta,
            stochastic_delta=components.stochastic_delta,
            total=total_time,
        )

    def _calculate_setup_delta(
        self,
        inputs: LapTimeInputs,
        effects: SetupEffects,
    ) -> float:
        """Calculate setup contribution to lap time delta (fraction)."""
        base_time = inputs.base_lap_time
        track = inputs.track

        # Get track-specific contributions
        contributions = effects.get_lap_time_contributions(base_time)

        # Apply track scaling (direct physical descriptors, not inverted category)
        aero_scaling = track.aero_sensitivity / 50.0
        mechanical_scaling = (track.traction_energy + track.braking_energy) / 100.0
        tyre_scaling = (track.front_tyre_stress + track.rear_tyre_stress) / 100.0

        # Apply sensitivities
        aero_contrib = contributions["aero"] * aero_scaling * self.setup_downforce_sensitivity
        mechanical_contrib = contributions["mechanical"] * mechanical_scaling * self.setup_mechanical_sensitivity  # noqa: E501
        tyre_contrib = contributions["tyre"] * tyre_scaling * self.setup_tyre_sensitivity

        # Total setup contribution as fraction of lap time
        total_setup_seconds = aero_contrib + mechanical_contrib + tyre_contrib
        setup_delta = total_setup_seconds / base_time

        return setup_delta

    def calculate_lap_time(self, inputs: LapTimeInputs) -> LapTimeComponents:
        """Override to optionally include setup if present in inputs."""
        # Check if setup is attached to inputs (duck typing)
        setup = getattr(inputs, "setup", None)
        setup_effects = getattr(inputs, "setup_effects", None)

        if setup is not None or setup_effects is not None:
            return self.calculate_lap_time_with_setup(inputs, setup, setup_effects)

        return super().calculate_lap_time(inputs)


def create_setup_aware_inputs(
    base_inputs: LapTimeInputs,
    setup: SetupState,
    car: Car,
    track: Track,
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
) -> LapTimeInputs:
    """Create LapTimeInputs with setup effects attached."""
    # Compute setup effects
    engine = SetupEngine(evidence_tier=evidence_tier)
    effects = engine.compute_effects(setup, car, track)

    # Apply effects to car
    adjusted_car = engine.apply_to_car(car, effects)

    # Create new inputs with adjusted car and setup attached
    new_inputs = LapTimeInputs(
        base_lap_time=base_inputs.base_lap_time,
        car=adjusted_car,
        engine_power_kw=base_inputs.engine_power_kw,
        driver=base_inputs.driver,
        driver_effective_skill=base_inputs.driver_effective_skill,
        compound=base_inputs.compound,
        tyre_spec=base_inputs.tyre_spec,
        tyre_age_laps=base_inputs.tyre_age_laps,
        tyre_wear=base_inputs.tyre_wear,
        tyre_temp=base_inputs.tyre_temp,
        fuel_mass=base_inputs.fuel_mass,
        fuel_per_lap=base_inputs.fuel_per_lap,
        track=base_inputs.track,
        track_evolution=base_inputs.track_evolution,
        track_grip=base_inputs.track_grip,
        weather=base_inputs.weather,
        is_qualifying=base_inputs.is_qualifying,
        is_race_start=base_inputs.is_race_start,
        is_safety_car=base_inputs.is_safety_car,
        is_vsc=base_inputs.is_vsc,
        drs_active=base_inputs.drs_active,
        ers_mode=base_inputs.ers_mode,
        in_traffic=base_inputs.in_traffic,
        traffic_loss=base_inputs.traffic_loss,
        aero_damage=base_inputs.aero_damage,
        mechanical_damage=base_inputs.mechanical_damage,
        rng=base_inputs.rng,
    )

    # Attach setup and effects for the model to use
    new_inputs.setup = setup
    new_inputs.setup_effects = effects

    return new_inputs


def compute_setup_lap_time_delta(
    setup: SetupState,
    car: Car,
    track: Track,
    base_lap_time: float,
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
) -> dict[str, float]:
    """Compute setup lap time contribution breakdown (for analysis)."""
    engine = SetupEngine(evidence_tier=evidence_tier)
    effects = engine.compute_effects(setup, car, track)
    contributions = engine.compute_lap_time_delta(effects, base_lap_time, track)

    return {
        "setup_id": setup.setup_id,
        "aero_contribution_sec": contributions["aero"],
        "mechanical_contribution_sec": contributions["mechanical"],
        "tyre_contribution_sec": contributions["tyre"],
        "total_contribution_sec": contributions["total"],
        "evidence_tier": evidence_tier.value,
        "effects_evidence": effects.aero_evidence.to_dict(),
    }
