"""Phase 20 — Setup models: parameters, constraints, effects, evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# NOTE: fingerprint import is lazy (inside methods) to avoid circular import
# with fingerprint.py which needs SetupState for typing.


class EvidenceTier(str, Enum):
    """Evidence tier for setup parameters and effects.

    CALIBRATED: Empirically calibrated from historical data with quantified uncertainty
    LIMITED: Some empirical support but limited sample size or scope
    PRIOR_ONLY: Based on physical principles/priors only, no direct empirical calibration
    NON_IDENTIFIABLE: Cannot be identified from available data (confounded)
    NOT_AVAILABLE: Not implemented / no model for this effect
    """

    CALIBRATED = "CALIBRATED"
    LIMITED = "LIMITED"
    PRIOR_ONLY = "PRIOR_ONLY"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ConstraintType(str, Enum):
    """Type of constraint on a setup parameter."""

    MODEL_PHYSICAL = "MODEL_PHYSICAL"  # Hard physical/model limit
    REGULATORY = "REGULATORY"  # Regulatory limit (era-dependent)
    DATA_SUPPORTED = "DATA_SUPPORTED"  # Range supported by calibration data
    USER_DEFINED = "USER_DEFINED"  # User-specified constraint


class SetupMode(str, Enum):
    """Mode of setup usage."""

    HISTORICAL = "historical"  # Replay with historical/baseline setup
    COUNTERFACTUAL = "counterfactual"  # Historical baseline vs modified
    HYPOTHETICAL = "hypothetical"  # Future/what-if scenario
    FUTURE = "future"  # Future race with user-defined setup


@dataclass
class ParameterEvidence:
    """Evidence metadata for a single setup parameter."""

    tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    source: str = ""  # e.g., "prior", "calibration_2024", "regulation_2022"
    calibration_date: str | None = None
    sample_size: int | None = None
    uncertainty: float | None = None  # Relative uncertainty if quantified
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "source": self.source,
            "calibration_date": self.calibration_date,
            "sample_size": self.sample_size,
            "uncertainty": self.uncertainty,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParameterEvidence:
        return cls(
            tier=EvidenceTier(data.get("tier", "PRIOR_ONLY")),
            source=data.get("source", ""),
            calibration_date=data.get("calibration_date"),
            sample_size=data.get("sample_size"),
            uncertainty=data.get("uncertainty"),
            notes=data.get("notes", ""),
        )


class SetupParameter(BaseModel):
    """Single setup parameter with value, bounds, and evidence."""

    name: str
    value: float
    minimum: float
    maximum: float
    step: float = 0.5
    unit: str = ""
    evidence: ParameterEvidence = Field(default_factory=ParameterEvidence)
    constraint_type: ConstraintType = ConstraintType.MODEL_PHYSICAL
    era_applicability: dict[str, bool] = Field(default_factory=dict)  # era -> allowed

    model_config = {"use_enum_values": True}

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float, info) -> float:
        # Validation happens in SetupValidator, not here
        return v

    def is_valid(self) -> bool:
        """Check if value is within bounds."""
        return self.minimum <= self.value <= self.maximum

    def clamp(self) -> float:
        """Return clamped value within bounds."""
        return max(self.minimum, min(self.maximum, self.value))

    def get_evidence_tier(self) -> EvidenceTier:
        return self.evidence.tier


class SetupParameters(BaseModel):
    """Complete set of setup parameters for a car."""

    # Aero
    front_wing: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="front_wing",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=0.5,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    rear_wing: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="rear_wing",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=0.5,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Ride height / platform
    ride_height_front: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="ride_height_front",
            value=20.0,
            minimum=10.0,
            maximum=50.0,
            step=1.0,
            unit="mm",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    ride_height_rear: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="ride_height_rear",
            value=30.0,
            minimum=15.0,
            maximum=60.0,
            step=1.0,
            unit="mm",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Suspension
    front_anti_roll: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="front_anti_roll",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=1.0,
            unit="stiffness_index",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    rear_anti_roll: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="rear_anti_roll",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=1.0,
            unit="stiffness_index",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    front_spring: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="front_spring",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=1.0,
            unit="stiffness_index",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    rear_spring: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="rear_spring",
            value=5.0,
            minimum=1.0,
            maximum=10.0,
            step=1.0,
            unit="stiffness_index",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Braking
    brake_bias: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="brake_bias",
            value=55.0,
            minimum=50.0,
            maximum=65.0,
            step=0.5,
            unit="%front",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Differential
    diff_entry: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="diff_entry",
            value=50.0,
            minimum=0.0,
            maximum=100.0,
            step=5.0,
            unit="%",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    diff_mid: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="diff_mid",
            value=50.0,
            minimum=0.0,
            maximum=100.0,
            step=5.0,
            unit="%",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    diff_exit: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="diff_exit",
            value=50.0,
            minimum=0.0,
            maximum=100.0,
            step=5.0,
            unit="%",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Geometry
    front_camber: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="front_camber",
            value=-3.0,
            minimum=-5.0,
            maximum=-1.0,
            step=0.1,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    rear_camber: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="rear_camber",
            value=-2.0,
            minimum=-4.0,
            maximum=-0.5,
            step=0.1,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    front_toe: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="front_toe",
            value=0.1,
            minimum=-0.5,
            maximum=0.5,
            step=0.05,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    rear_toe: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="rear_toe",
            value=0.2,
            minimum=-0.2,
            maximum=0.5,
            step=0.05,
            unit="degrees",
            evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    # Tyre
    tyre_pressure_front: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="tyre_pressure_front",
            value=22.0,
            minimum=18.0,
            maximum=28.0,
            step=0.5,
            unit="psi",
            evidence=ParameterEvidence(tier=EvidenceTier.NON_IDENTIFIABLE, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )
    tyre_pressure_rear: SetupParameter = Field(
        default_factory=lambda: SetupParameter(
            name="tyre_pressure_rear",
            value=20.0,
            minimum=18.0,
            maximum=28.0,
            step=0.5,
            unit="psi",
            evidence=ParameterEvidence(tier=EvidenceTier.NON_IDENTIFIABLE, source="prior"),
            constraint_type=ConstraintType.MODEL_PHYSICAL,
        )
    )

    model_config = {"use_enum_values": True, "arbitrary_types_allowed": True}

    def get_all(self) -> dict[str, SetupParameter]:
        """Get all parameters as dict of SetupParameter objects."""
        result: dict[str, SetupParameter] = {}
        for name in type(self).model_fields:
            val = getattr(self, name, None)
            if isinstance(val, SetupParameter):
                result[name] = val
        return result

    def get_values(self) -> dict[str, float]:
        """Get parameter names -> values."""
        return {k: v.value for k, v in self.get_all().items()}

    def get_evidence_map(self) -> dict[str, EvidenceTier]:
        """Get parameter names -> evidence tiers."""
        out: dict[str, EvidenceTier] = {}
        for k, v in self.get_all().items():
            tier = v.evidence.tier
            # With use_enum_values, tier may already be a plain string
            if isinstance(tier, EvidenceTier):
                out[k] = tier
            else:
                try:
                    out[k] = EvidenceTier(str(tier))
                except Exception:
                    out[k] = EvidenceTier.PRIOR_ONLY
        return out

    def set_value(self, name: str, value: float) -> bool:
        """Set parameter value if it exists."""
        if hasattr(self, name):
            param = getattr(self, name)
            param.value = value
            return True
        return False


class SetupConstraints(BaseModel):
    """Constraints on setup parameters, potentially era/track dependent."""

    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # e.g., {"front_wing": {"minimum": 1, "maximum": 10, "type": "MODEL_PHYSICAL", "era": "2022-2026"}}

    model_config = {"use_enum_values": True}

    def get_constraint(self, param_name: str, era: str | None = None) -> dict[str, Any] | None:
        """Get constraint for a parameter, optionally filtered by era."""
        if param_name not in self.parameters:
            return None
        constraint = self.parameters[param_name]
        if era and "era" in constraint:
            constraint_era = constraint["era"]
            if isinstance(constraint_era, str) and constraint_era != era:
                # Could add era hierarchy logic here
                pass
        return constraint

    def validate_all(self, params: SetupParameters) -> list[str]:
        """Validate all parameters against constraints. Returns list of violations."""
        violations = []
        for name, param in params.get_all().items():
            constraint = self.get_constraint(name)
            if constraint:
                if param.value < constraint.get("minimum", param.minimum):
                    violations.append(f"{name}: value {param.value} below minimum {constraint['minimum']}")  # noqa: E501
                if param.value > constraint.get("maximum", param.maximum):
                    violations.append(f"{name}: value {param.value} above maximum {constraint['maximum']}")  # noqa: E501
        return violations


class SetupEffects(BaseModel):
    """Interpretable intermediate vehicle characteristics derived from setup.

    These are the causal intermediates between setup parameters and lap time.
    Each effect carries evidence metadata.
    """

    # Aero effects
    downforce_change: float = 0.0  # % change vs baseline
    drag_change: float = 0.0  # % change vs baseline
    aero_balance_change: float = 0.0  # Front/rear balance shift (%)

    # Mechanical effects
    cornering_stiffness_change: float = 0.0  # % change
    traction_change: float = 0.0  # % change
    braking_stability_change: float = 0.0  # % change
    ride_compliance_change: float = 0.0  # % change

    # Tyre interaction effects
    front_tyre_load_change: float = 0.0  # % change
    rear_tyre_load_change: float = 0.0  # % change
    front_tyre_deg_change: float = 0.0  # % change in degradation rate
    rear_tyre_deg_change: float = 0.0  # % change in degradation rate
    tyre_warmup_change: float = 0.0  # % change in warmup speed

    # Track-specific modifiers (populated by SetupEngine)
    track_high_speed_factor: float = 1.0  # Multiplier for high-speed corners
    track_low_speed_factor: float = 1.0  # Multiplier for low-speed corners
    track_straight_factor: float = 1.0  # Multiplier for straight-line speed
    track_braking_factor: float = 1.0  # Multiplier for braking zones
    track_traction_factor: float = 1.0  # Multiplier for traction zones

    # Evidence for each effect category
    aero_evidence: ParameterEvidence = Field(default_factory=lambda: ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY))  # noqa: E501
    mechanical_evidence: ParameterEvidence = Field(default_factory=lambda: ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY))  # noqa: E501
    tyre_evidence: ParameterEvidence = Field(default_factory=lambda: ParameterEvidence(tier=EvidenceTier.NON_IDENTIFIABLE))  # noqa: E501

    model_config = {"use_enum_values": True}

    def get_lap_time_contributions(self, base_lap_time: float) -> dict[str, float]:
        """Estimate lap time contribution from each effect category (seconds).

        PRIOR_ONLY scaling: a full wing sweep (delta 9 -> ~15% downforce)
        maps to O(0.5-1.0s) on a 90s lap, i.e. large setup swings are
        detectable but small trims are within noise. All factors are priors,
        NOT calibrated; uncertainty is broad by design.
        """
        contributions = {}

        # Aero: downforce helps (negative = faster), drag hurts (positive = slower).
        # 1% downforce ~= -0.05% lap time; 1% drag ~= +0.06% lap time.
        aero_effect = (-self.downforce_change * 0.05 + self.drag_change * 0.06) * base_lap_time
        contributions["aero"] = aero_effect

        # Mechanical: stiffness/traction/braking help (negative = faster).
        mechanical_effect = -(
            self.cornering_stiffness_change * 0.03
            + self.traction_change * 0.02
            + self.braking_stability_change * 0.015
        ) * base_lap_time
        contributions["mechanical"] = mechanical_effect

        # Tyre: load helps grip (negative), degradation hurts (positive).
        # Weakest, NON_IDENTIFIABLE.
        tyre_effect = (
            -self.front_tyre_load_change * 0.01
            - self.rear_tyre_load_change * 0.01
            + self.front_tyre_deg_change * 0.02
            + self.rear_tyre_deg_change * 0.02
        ) * base_lap_time
        contributions["tyre"] = tyre_effect

        return contributions

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict including evidence."""
        data = self.model_dump()
        data["aero_evidence"] = self.aero_evidence.to_dict()
        data["mechanical_evidence"] = self.mechanical_evidence.to_dict()
        data["tyre_evidence"] = self.tyre_evidence.to_dict()
        return data


class SetupEvidence(BaseModel):
    """Aggregate evidence assessment for a complete setup."""

    overall_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    parameter_tiers: dict[str, EvidenceTier] = Field(default_factory=dict)
    effect_tiers: dict[str, EvidenceTier] = Field(default_factory=dict)
    calibration_sources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    as_of: str | None = None  # Temporal context for historical mode

    model_config = {"use_enum_values": True}

    def add_limitation(self, limitation: str) -> None:
        if limitation not in self.limitations:
            self.limitations.append(limitation)

    def get_summary(self) -> str:
        """Human-readable evidence summary."""
        calibrated = sum(1 for t in self.parameter_tiers.values() if t == EvidenceTier.CALIBRATED)
        limited = sum(1 for t in self.parameter_tiers.values() if t == EvidenceTier.LIMITED)
        prior = sum(1 for t in self.parameter_tiers.values() if t == EvidenceTier.PRIOR_ONLY)
        non_id = sum(1 for t in self.parameter_tiers.values() if t == EvidenceTier.NON_IDENTIFIABLE)
        total = len(self.parameter_tiers)
        return f"Calibrated: {calibrated}/{total}, Limited: {limited}/{total}, Prior-only: {prior}/{total}, Non-identifiable: {non_id}/{total}"  # noqa: E501


class SetupState(BaseModel):
    """Canonical setup representation — serializable, reproducible, fingerprinted."""

    # Identity
    setup_id: str
    car_id: str
    constructor_id: str
    season: str  # e.g., "2024", "2022-2026"
    track_id: str | None = None

    # Parameters and constraints
    parameters: SetupParameters = Field(default_factory=SetupParameters)
    constraints: SetupConstraints = Field(default_factory=SetupConstraints)

    # Derived effects (populated by SetupEngine)
    effects: SetupEffects | None = None

    # Evidence and provenance
    evidence: SetupEvidence = Field(default_factory=SetupEvidence)
    model_version: str = "setup-v1.0.0"
    provenance: dict[str, Any] = Field(default_factory=dict)

    # Mode and temporal context
    mode: SetupMode = SetupMode.HYPOTHETICAL
    as_of: str | None = None  # For historical/counterfactual: data cutoff

    # Fingerprint (computed)
    fingerprint: str | None = None

    model_config = {"use_enum_values": True, "arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        if self.fingerprint is None:
            from app.simulation.setup.fingerprint import setup_fingerprint as _fp

            self.fingerprint = _fp(self)

    def compute_fingerprint(self) -> str:
        """Compute deterministic fingerprint of this setup."""
        from app.simulation.setup.fingerprint import setup_fingerprint as _fp

        self.fingerprint = _fp(self)
        return self.fingerprint

    def get_baseline_deviation(self) -> dict[str, float]:
        """Get deviation from baseline setup values."""
        baseline = create_baseline_setup(car_id=self.car_id, track_id=self.track_id or "")
        deviations = {}
        for name, param in self.parameters.get_all().items():
            baseline_param = baseline.parameters.get_all().get(name)
            if baseline_param:
                deviations[name] = param.value - baseline_param.value
        return deviations

    def to_scenario_modifier(self) -> dict[str, Any]:
        """Convert to hypothetical_modifiers for Scenario."""
        mode_val = self.mode.value if hasattr(self.mode, "value") else str(self.mode)
        return {
            "setup": {
                "setup_id": self.setup_id,
                "parameters": self.parameters.get_values(),
                "mode": mode_val,
                "fingerprint": self.fingerprint,
            }
        }


# Default baseline setup factory
def create_baseline_setup(
    car_id: str = "default",
    constructor_id: str = "default",
    season: str = "2024",
    track_id: str = "monaco",
    mode: SetupMode = SetupMode.HYPOTHETICAL,
) -> SetupState:
    """Create a baseline setup that approximates Phase 19 default behavior.

    This setup should produce lap times close to the pre-setup simulation.
    """
    params = SetupParameters()

    # Set baseline values that produce near-neutral effects
    # These are chosen so that effects are minimal
    baseline_values = {
        "front_wing": 5.0,
        "rear_wing": 5.0,
        "ride_height_front": 20.0,
        "ride_height_rear": 30.0,
        "front_anti_roll": 5.0,
        "rear_anti_roll": 5.0,
        "front_spring": 5.0,
        "rear_spring": 5.0,
        "brake_bias": 55.0,
        "diff_entry": 50.0,
        "diff_mid": 50.0,
        "diff_exit": 50.0,
        "front_camber": -3.0,
        "rear_camber": -2.0,
        "front_toe": 0.1,
        "rear_toe": 0.2,
        "tyre_pressure_front": 22.0,
        "tyre_pressure_rear": 20.0,
    }

    for name, value in baseline_values.items():
        if hasattr(params, name):
            getattr(params, name).value = value

    # Evidence: all PRIOR_ONLY or NON_IDENTIFIABLE for baseline
    evidence = SetupEvidence(
        overall_tier=EvidenceTier.PRIOR_ONLY,
        parameter_tiers={name: EvidenceTier.PRIOR_ONLY for name in baseline_values},
        limitations=[
            "Baseline setup uses prior-only coefficients",
            "No historical setup data available for calibration",
            "Track-specific effects not calibrated",
            "Tyre interaction effects are NON_IDENTIFIABLE",
        ],
    )

    provenance = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "phase20_baseline_factory",
        "car_id": car_id,
        "track_id": track_id,
        "note": "Default baseline preserving Phase 19 behavior",
    }

    return SetupState(
        setup_id=f"baseline_{car_id}_{track_id}",
        car_id=car_id,
        constructor_id=constructor_id,
        season=season,
        track_id=track_id,
        parameters=params,
        evidence=evidence,
        provenance=provenance,
        mode=mode,
    )


def create_setup_from_dict(
    setup_dict: dict[str, float],
    car_id: str = "default",
    constructor_id: str = "default",
    season: str = "2024",
    track_id: str | None = None,
    mode: SetupMode = SetupMode.HYPOTHETICAL,
) -> SetupState:
    """Create a SetupState from a simple parameter dict."""
    baseline = create_baseline_setup(car_id, constructor_id, season, track_id or "unknown", mode)
    for name, value in setup_dict.items():
        baseline.parameters.set_value(name, value)
    baseline.setup_id = f"custom_{car_id}_{track_id or 'unknown'}"
    baseline.compute_fingerprint()
    return baseline


# Constraint presets for different eras
def get_era_constraints(era: str) -> SetupConstraints:
    """Get regulatory/physical constraints for an era."""
    constraints = SetupConstraints()

    # Base physical constraints (same across eras)
    base_params = {
        "front_wing": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "rear_wing": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "ride_height_front": {"minimum": 10.0, "maximum": 50.0, "type": ConstraintType.MODEL_PHYSICAL},  # noqa: E501
        "ride_height_rear": {"minimum": 15.0, "maximum": 60.0, "type": ConstraintType.MODEL_PHYSICAL},  # noqa: E501
        "front_anti_roll": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "rear_anti_roll": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "front_spring": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "rear_spring": {"minimum": 1.0, "maximum": 10.0, "type": ConstraintType.MODEL_PHYSICAL},
        "brake_bias": {"minimum": 50.0, "maximum": 65.0, "type": ConstraintType.MODEL_PHYSICAL},
        "diff_entry": {"minimum": 0.0, "maximum": 100.0, "type": ConstraintType.MODEL_PHYSICAL},
        "diff_mid": {"minimum": 0.0, "maximum": 100.0, "type": ConstraintType.MODEL_PHYSICAL},
        "diff_exit": {"minimum": 0.0, "maximum": 100.0, "type": ConstraintType.MODEL_PHYSICAL},
        "front_camber": {"minimum": -5.0, "maximum": -1.0, "type": ConstraintType.MODEL_PHYSICAL},
        "rear_camber": {"minimum": -4.0, "maximum": -0.5, "type": ConstraintType.MODEL_PHYSICAL},
        "front_toe": {"minimum": -0.5, "maximum": 0.5, "type": ConstraintType.MODEL_PHYSICAL},
        "rear_toe": {"minimum": -0.2, "maximum": 0.5, "type": ConstraintType.MODEL_PHYSICAL},
        "tyre_pressure_front": {"minimum": 18.0, "maximum": 28.0, "type": ConstraintType.MODEL_PHYSICAL},  # noqa: E501
        "tyre_pressure_rear": {"minimum": 18.0, "maximum": 28.0, "type": ConstraintType.MODEL_PHYSICAL},  # noqa: E501
    }

    # Era-specific regulatory constraints (Phase 22 will expand)
    if era in ("2022-2026", "2024", "2023", "2022"):
        # Modern ground-effect era: ride height more constrained
        base_params["ride_height_front"]["minimum"] = 15.0
        base_params["ride_height_rear"]["minimum"] = 25.0
    elif era in ("2014-2021", "2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021"):
        # Hybrid V6 era: more flexible ride heights
        pass
    # Pre-2014: even more flexible

    constraints.parameters = base_params
    return constraints
