"""Phase 20 — Setup Engine: translates setup parameters into vehicle effects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.simulation.models.car import Car
from app.simulation.models.track import Track
from app.simulation.setup.models import (
    SetupState,
    SetupParameters,
    SetupEffects,
    SetupEvidence,
    EvidenceTier,
    ParameterEvidence,
    create_baseline_setup,
)


@dataclass
class SetupCoefficients:
    """Coefficients mapping setup parameters to vehicle effects.

    These are PRIOR_ONLY unless calibrated. Each coefficient represents
    the effect per unit of parameter change from baseline.

    Structure:
        effect_name: {param_name: coefficient_per_unit}

    Coefficients are dimensionless multipliers on the base car characteristic.
    """

    # Aero coefficients (per degree of wing, per mm of ride height)
    downforce: dict[str, float] = None
    drag: dict[str, float] = None
    aero_balance: dict[str, float] = None

    # Mechanical coefficients
    cornering_stiffness: dict[str, float] = None
    traction: dict[str, float] = None
    braking_stability: dict[str, float] = None
    ride_compliance: dict[str, float] = None

    # Tyre interaction coefficients
    front_tyre_load: dict[str, float] = None
    rear_tyre_load: dict[str, float] = None
    front_tyre_deg: dict[str, float] = None
    rear_tyre_deg: dict[str, float] = None
    tyre_warmup: dict[str, float] = None

    def __post_init__(self):
        if self.downforce is None:
            self.downforce = {}
        if self.drag is None:
            self.drag = {}
        if self.aero_balance is None:
            self.aero_balance = {}
        if self.cornering_stiffness is None:
            self.cornering_stiffness = {}
        if self.traction is None:
            self.traction = {}
        if self.braking_stability is None:
            self.braking_stability = {}
        if self.ride_compliance is None:
            self.ride_compliance = {}
        if self.front_tyre_load is None:
            self.front_tyre_load = {}
        if self.rear_tyre_load is None:
            self.rear_tyre_load = {}
        if self.front_tyre_deg is None:
            self.front_tyre_deg = {}
        if self.rear_tyre_deg is None:
            self.rear_tyre_deg = {}
        if self.tyre_warmup is None:
            self.tyre_warmup = {}


def get_default_coefficients() -> SetupCoefficients:
    """Get default prior-only coefficients for setup -> effects mapping.

    These coefficients represent physical priors:
    - More wing angle -> more downforce, more drag
    - Lower ride height -> more ground effect downforce, less drag (to a point)
    - Stiffer suspension -> better response, worse compliance
    - Brake bias -> braking stability distribution
    - Camber -> cornering grip vs straight-line wear
    - Tyre pressure -> contact patch, warmup, degradation

    ALL COEFFICIENTS ARE PRIOR_ONLY unless explicitly calibrated.
    """
    coeffs = SetupCoefficients()

    # Aero: wing angles (per degree from baseline 5.0)
    coeffs.downforce = {
        "front_wing": 0.015,  # 1.5% downforce per degree
        "rear_wing": 0.018,  # 1.8% downforce per degree (rear wing more effective)
        "ride_height_front": -0.008,  # Lower front = more ground effect
        "ride_height_rear": -0.010,  # Lower rear = more diffuser effect
    }
    coeffs.drag = {
        "front_wing": 0.012,  # 1.2% drag per degree
        "rear_wing": 0.015,  # 1.5% drag per degree
        "ride_height_front": 0.003,  # Lower = slightly more drag (ground effect)
        "ride_height_rear": 0.002,
    }
    coeffs.aero_balance = {
        "front_wing": 0.02,  # Front wing shifts balance forward
        "rear_wing": -0.025,  # Rear wing shifts balance rearward
        "ride_height_front": -0.01,  # Lower front = more front downforce
        "ride_height_rear": 0.015,  # Lower rear = more rear downforce
    }

    # Mechanical: suspension (per stiffness index from baseline 5.0)
    coeffs.cornering_stiffness = {
        "front_anti_roll": 0.015,
        "rear_anti_roll": 0.012,
        "front_spring": 0.010,
        "rear_spring": 0.008,
        "front_camber": 0.020,  # Per degree (negative camber helps cornering)
        "rear_camber": 0.015,
    }
    coeffs.traction = {
        "rear_anti_roll": -0.008,  # Stiffer rear ARB reduces traction
        "rear_spring": -0.006,
        "diff_exit": 0.001,  # Per % lock
        "rear_camber": -0.010,  # Negative camber hurts traction
        "rear_toe": 0.005,  # Toe-in helps traction
    }
    coeffs.braking_stability = {
        "brake_bias": 0.005,  # Per % front bias
        "front_anti_roll": 0.008,
        "front_spring": 0.006,
        "front_toe": 0.010,  # Toe-out helps turn-in under braking
    }
    coeffs.ride_compliance = {
        "front_spring": -0.015,
        "rear_spring": -0.012,
        "front_anti_roll": -0.008,
        "rear_anti_roll": -0.006,
        "ride_height_front": 0.005,  # Higher = more compliance
        "ride_height_rear": 0.005,
    }

    # Tyre interaction (mostly NON_IDENTIFIABLE / PRIOR_ONLY)
    coeffs.front_tyre_load = {
        "front_wing": 0.008,
        "front_anti_roll": 0.005,
        "front_spring": 0.004,
        "front_camber": -0.006,  # Negative camber increases outer tyre load
        "ride_height_front": -0.003,
    }
    coeffs.rear_tyre_load = {
        "rear_wing": 0.010,
        "rear_anti_roll": 0.006,
        "rear_spring": 0.005,
        "rear_camber": -0.005,
        "ride_height_rear": -0.004,
        "diff_entry": 0.0005,
    }
    coeffs.front_tyre_deg = {
        "front_camber": 0.015,  # More camber = more wear on outside
        "front_toe": 0.020,  # Toe-out increases scrub
        "front_anti_roll": 0.005,
        "front_spring": 0.004,
        "tyre_pressure_front": -0.008,  # Higher pressure = less wear (to a point)
    }
    coeffs.rear_tyre_deg = {
        "rear_camber": 0.012,
        "rear_toe": 0.015,
        "rear_anti_roll": 0.004,
        "rear_spring": 0.003,
        "diff_exit": 0.0008,  # More lock = more rear tyre stress
        "tyre_pressure_rear": -0.006,
    }
    coeffs.tyre_warmup = {
        "front_camber": -0.010,  # Camber helps warmup (more contact patch in corners)
        "rear_camber": -0.008,
        "front_spring": 0.005,  # Stiffer = faster warmup
        "rear_spring": 0.004,
        "tyre_pressure_front": 0.005,
        "tyre_pressure_rear": 0.004,
    }

    return coeffs


def get_track_modifiers(track: Track) -> dict[str, float]:
    """Get track-specific modifiers for setup effects.

    Returns multipliers for different track characteristics.

    NOTE: deliberately does NOT use Track.get_track_type_category(), whose
    high/low-downforce labels are inverted for corner-speed ratios
    (e.g. Monza classified as high_downforce). Instead modifiers are derived
    directly from physical track descriptors:
      - straight share (total_straight_length / length_km, longest straight,
        DRS zones) -> straight_factor
      - slow-corner share (hairpin+slow+chicane) -> low_speed_factor
      - fast-corner share (fast+high_speed) + aero_sensitivity -> high_speed_factor
      - braking_energy / braking zones -> braking_factor
      - traction_energy -> traction_factor

    All tiers PRIOR_ONLY.
    """
    length = max(0.5, float(getattr(track, "length_km", 5.0) or 5.0))
    # Prefer sector straight sum when available: total_straight_length_km
    # defaults to 2.5km which inflates short tracks (e.g. Monaco 3.3km).
    sector_straights = getattr(track, "sector_straight_lengths_km", None) or []
    try:
        sector_sum = float(sum(float(x) for x in sector_straights)) if sector_straights else 0.0
    except Exception:
        sector_sum = 0.0
    if sector_sum > 0:
        total_straight = sector_sum
    else:
        total_straight = float(getattr(track, "total_straight_length_km", 2.0) or 2.0)
    straight_share = max(0.0, min(1.0, total_straight / length))
    longest = float(getattr(track, "longest_straight_km", 1.0) or 1.0)
    # Prefer sector DRS sum when available.
    sector_drs = getattr(track, "sector_drs_zones", None) or []
    try:
        drs_sum = int(sum(int(x) for x in sector_drs)) if sector_drs else None
    except Exception:
        drs_sum = None
    drs_zones = drs_sum if drs_sum is not None else int(getattr(track, "drs_zones", 2) or 0)

    corner_dist = getattr(track, "corner_distribution", {}) or {}
    # Keys may be CornerType enums (use_enum_values may stringify); handle both.
    def _count(*names: str) -> int:
        total = 0
        for k, v in corner_dist.items():
            ks = getattr(k, "value", k)
            if ks in names:
                try:
                    total += int(v)
                except Exception:
                    pass
        return total

    n_slow = _count("hairpin", "slow", "chicane")
    n_fast = _count("fast", "high_speed")
    n_med = _count("medium", "double_apex")
    n_total = max(1, n_slow + n_fast + n_med)
    slow_share = n_slow / n_total
    fast_share = n_fast / n_total

    aero = float(getattr(track, "aero_sensitivity", 50.0) or 50.0) / 100.0  # 0..1
    braking_e = float(getattr(track, "braking_energy", 50.0) or 50.0) / 100.0
    traction_e = float(getattr(track, "traction_energy", 50.0) or 50.0) / 100.0
    tyre_stress = (
        float(getattr(track, "front_tyre_stress", 50.0) or 50.0)
        + float(getattr(track, "rear_tyre_stress", 50.0) or 50.0)
    ) / 200.0

    # Straight importance: high straight share, long straight, DRS, LOW aero sens.
    straight_factor = (
        0.55
        + 1.1 * straight_share
        + 0.18 * min(1.5, longest)
        + 0.06 * min(4, drs_zones)
        + 0.35 * (1.0 - aero)
    )
    # High-speed corner importance: fast share + aero sensitivity.
    high_speed_factor = 0.55 + 0.9 * fast_share + 0.7 * aero
    # Low-speed importance: slow share + traction demand.
    low_speed_factor = 0.60 + 0.9 * slow_share + 0.4 * traction_e
    # Braking importance.
    braking_factor = 0.70 + 0.7 * braking_e + 0.02 * float(getattr(track, "number_of_braking_zones", 8) or 8)  # noqa: E501
    # Traction importance: traction energy + tyre stress.
    traction_factor = 0.70 + 0.6 * traction_e + 0.3 * tyre_stress

    return {
        "high_speed_factor": float(high_speed_factor),
        "low_speed_factor": float(low_speed_factor),
        "straight_factor": float(straight_factor),
        "braking_factor": float(braking_factor),
        "traction_factor": float(traction_factor),
    }


class SetupEngine:
    """Engine that computes vehicle effects from setup parameters."""

    def __init__(
        self,
        coefficients: SetupCoefficients | None = None,
        evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
    ):
        self.coefficients = coefficients or get_default_coefficients()
        self.default_evidence_tier = evidence_tier
        self._baseline_params = None

    def _get_baseline(self, car_id: str, track_id: str) -> SetupParameters:
        """Get baseline parameters for comparison."""
        if self._baseline_params is None:
            baseline_state = create_baseline_setup(car_id=car_id, track_id=track_id)
            self._baseline_params = baseline_state.parameters
        return self._baseline_params

    def compute_effects(
        self,
        setup: SetupState,
        car: Car,
        track: Track,
    ) -> SetupEffects:
        """Compute vehicle effects from setup parameters."""
        params = setup.parameters
        baseline = self._get_baseline(setup.car_id, setup.track_id or track.id)

        # Compute parameter deltas from baseline
        deltas = {}
        for name, param in params.get_all().items():
            baseline_param = baseline.get_all().get(name)
            if baseline_param:
                deltas[name] = param.value - baseline_param.value
            else:
                deltas[name] = 0.0

        # Get track modifiers
        track_modifiers = get_track_modifiers(track)

        # Compute each effect category
        effects = SetupEffects()

        # Aero effects
        effects.downforce_change = self._compute_effect(deltas, self.coefficients.downforce)
        effects.drag_change = self._compute_effect(deltas, self.coefficients.drag)
        effects.aero_balance_change = self._compute_effect(deltas, self.coefficients.aero_balance)

        # Mechanical effects
        effects.cornering_stiffness_change = self._compute_effect(deltas, self.coefficients.cornering_stiffness)  # noqa: E501
        effects.traction_change = self._compute_effect(deltas, self.coefficients.traction)
        effects.braking_stability_change = self._compute_effect(deltas, self.coefficients.braking_stability)  # noqa: E501
        effects.ride_compliance_change = self._compute_effect(deltas, self.coefficients.ride_compliance)  # noqa: E501

        # Tyre interaction effects
        effects.front_tyre_load_change = self._compute_effect(deltas, self.coefficients.front_tyre_load)  # noqa: E501
        effects.rear_tyre_load_change = self._compute_effect(deltas, self.coefficients.rear_tyre_load)  # noqa: E501
        effects.front_tyre_deg_change = self._compute_effect(deltas, self.coefficients.front_tyre_deg)  # noqa: E501
        effects.rear_tyre_deg_change = self._compute_effect(deltas, self.coefficients.rear_tyre_deg)
        effects.tyre_warmup_change = self._compute_effect(deltas, self.coefficients.tyre_warmup)

        # Track-specific modifiers
        effects.track_high_speed_factor = track_modifiers["high_speed_factor"]
        effects.track_low_speed_factor = track_modifiers["low_speed_factor"]
        effects.track_straight_factor = track_modifiers["straight_factor"]
        effects.track_braking_factor = track_modifiers["braking_factor"]
        effects.track_traction_factor = track_modifiers["traction_factor"]

        # Evidence
        effects.aero_evidence = ParameterEvidence(
            tier=self.default_evidence_tier,
            source="prior_coefficients",
            notes="Prior-only coefficients; not empirically calibrated",
        )
        effects.mechanical_evidence = ParameterEvidence(
            tier=self.default_evidence_tier,
            source="prior_coefficients",
            notes="Prior-only coefficients; not empirically calibrated",
        )
        effects.tyre_evidence = ParameterEvidence(
            tier=EvidenceTier.NON_IDENTIFIABLE,
            source="prior_coefficients",
            notes="Tyre interaction effects not identifiable from current data",
        )

        return effects

    def _compute_effect(self, deltas: dict[str, float], coeffs: dict[str, float]) -> float:
        """Compute effect as sum of delta * coefficient."""
        total = 0.0
        for param, delta in deltas.items():
            if param in coeffs:
                total += delta * coeffs[param]
        return total

    def compute_lap_time_delta(
        self,
        effects: SetupEffects,
        base_lap_time: float,
        track: Track,
    ) -> dict[str, float]:
        """Estimate lap time contribution from setup effects (seconds)."""
        contributions = effects.get_lap_time_contributions(base_lap_time)

        # Apply track-specific scaling
        track_type = track.get_track_type_category()

        # Aero effect scales with track aero sensitivity
        aero_scaling = track.aero_sensitivity / 50.0
        contributions["aero"] *= aero_scaling

        # Mechanical effect scales with cornering/traction demands
        mechanical_scaling = (track.traction_energy + track.braking_energy) / 100.0
        contributions["mechanical"] *= mechanical_scaling

        # Tyre effect scales with track tyre stress
        tyre_scaling = (track.front_tyre_stress + track.rear_tyre_stress) / 100.0
        contributions["tyre"] *= tyre_scaling

        # Total
        contributions["total"] = sum(contributions.values())

        return contributions

    def apply_to_car(self, car: Car, effects: SetupEffects) -> Car:
        """Apply setup effects to a car model (returns modified copy).

        This creates a new Car with adjusted characteristics based on setup.
        """
        new_car = car.model_copy(deep=True)

        # Aero adjustments
        new_car.overall_downforce = max(0, min(100, new_car.overall_downforce * (1 + effects.downforce_change)))  # noqa: E501
        new_car.front_downforce = max(0, min(100, new_car.front_downforce * (1 + effects.downforce_change + effects.aero_balance_change)))  # noqa: E501
        new_car.rear_downforce = max(0, min(100, new_car.rear_downforce * (1 + effects.downforce_change - effects.aero_balance_change)))  # noqa: E501
        new_car.aero_efficiency = max(0, min(100, new_car.aero_efficiency * (1 - effects.drag_change * 0.5)))  # noqa: E501

        # Mechanical adjustments
        new_car.mechanical_grip = max(0, min(100, new_car.mechanical_grip * (1 + effects.cornering_stiffness_change)))  # noqa: E501
        new_car.traction = max(0, min(100, new_car.traction * (1 + effects.traction_change)))
        new_car.braking_stability = max(0, min(100, new_car.braking_stability * (1 + effects.braking_stability_change)))  # noqa: E501
        new_car.front_suspension = max(0, min(100, new_car.front_suspension * (1 + effects.ride_compliance_change)))  # noqa: E501
        new_car.rear_suspension = max(0, min(100, new_car.rear_suspension * (1 + effects.ride_compliance_change)))  # noqa: E501

        # Tyre interaction adjustments
        new_car.tyre_wear_front = max(0, min(100, new_car.tyre_wear_front * (1 - effects.front_tyre_deg_change)))  # noqa: E501
        new_car.tyre_wear_rear = max(0, min(100, new_car.tyre_wear_rear * (1 - effects.rear_tyre_deg_change)))  # noqa: E501
        new_car.tyre_warmup_speed = max(0, min(100, new_car.tyre_warmup_speed * (1 + effects.tyre_warmup_change)))  # noqa: E501
        new_car.front_rear_tyre_balance = max(-20, min(20, new_car.front_rear_tyre_balance + (effects.front_tyre_load_change - effects.rear_tyre_load_change) * 50))  # noqa: E501

        return new_car

    def get_effect_evidence_summary(self) -> dict[str, Any]:
        """Get summary of evidence tiers for all effects."""
        return {
            "aero": self.default_evidence_tier.value,
            "mechanical": self.default_evidence_tier.value,
            "tyre_interaction": EvidenceTier.NON_IDENTIFIABLE.value,
            "track_interaction": EvidenceTier.PRIOR_ONLY.value,
            "note": "All coefficients are PRIOR_ONLY unless explicitly calibrated",
        }


# Convenience function
def compute_setup_effects(
    setup: SetupState,
    car: Car,
    track: Track,
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
) -> SetupEffects:
    """Compute setup effects using default engine."""
    engine = SetupEngine(evidence_tier=evidence_tier)
    return engine.compute_effects(setup, car, track)
