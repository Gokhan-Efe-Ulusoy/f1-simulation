"""Phase 20 — Setup validation and constraint checking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.simulation.setup.models import (
    SetupState,
    SetupParameters,
    SetupConstraints,
    SetupParameter,
    EvidenceTier,
    ConstraintType,
    get_era_constraints,
)


@dataclass
class ValidationResult:
    """Result of setup validation."""

    is_valid: bool
    violations: list[str]
    warnings: list[str]
    parameter_status: dict[str, dict[str, Any]]  # param -> {valid, value, min, max, evidence_tier}

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violations": self.violations,
            "warnings": self.warnings,
            "parameter_status": self.parameter_status,
        }

    def add_violation(self, message: str) -> None:
        self.violations.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class SetupValidator:
    """Validates setup parameters against physical, model, and regulatory constraints."""

    def __init__(self, era: str | None = None, track_id: str | None = None):
        self.constraints = get_era_constraints(era or "2022-2026")
        self.track_id = track_id
        self.era = era or "2022-2026"

    def validate(self, setup: SetupState | SetupParameters) -> ValidationResult:
        """Validate a complete setup."""
        if isinstance(setup, SetupState):
            params = setup.parameters
            era = setup.season
            track_id = setup.track_id
        else:
            params = setup
            era = self.era
            track_id = self.track_id

        # Update constraints for era if different
        if era != self.era:
            self.constraints = get_era_constraints(era)
            self.era = era

        result = ValidationResult(
            is_valid=True,
            violations=[],
            warnings=[],
            parameter_status={},
        )

        for name, param in params.get_all().items():
            status = self._validate_parameter(param, name)
            result.parameter_status[name] = status

            if not status["valid"]:
                result.add_violation(f"{name}: {status['message']}")
            elif status.get("warning"):
                result.add_warning(f"{name}: {status['warning']}")

        # Cross-parameter validation
        self._validate_cross_parameters(params, result)

        # Track-specific validation
        if track_id:
            self._validate_track_specific(params, track_id, result)

        return result

    @staticmethod
    def _enum_val(v: Any) -> str:
        return getattr(v, "value", v) if not isinstance(v, str) else v

    def _validate_parameter(self, param: SetupParameter, name: str) -> dict[str, Any]:
        """Validate a single parameter."""
        status = {
            "valid": True,
            "value": param.value,
            "minimum": param.minimum,
            "maximum": param.maximum,
            "evidence_tier": self._enum_val(param.evidence.tier),
            "constraint_type": self._enum_val(param.constraint_type),
            "message": "",
            "warning": None,
        }

        # Bounds check
        if param.value < param.minimum:
            status["valid"] = False
            status["message"] = f"Value {param.value} below minimum {param.minimum}"
        elif param.value > param.maximum:
            status["valid"] = False
            status["message"] = f"Value {param.value} above maximum {param.maximum}"

        # Constraint check
        constraint = self.constraints.get_constraint(name)
        if constraint:
            c_min = constraint.get("minimum", param.minimum)
            c_max = constraint.get("maximum", param.maximum)
            if param.value < c_min:
                status["valid"] = False
                status["message"] = f"Value {param.value} below constraint minimum {c_min} ({constraint.get('type', 'unknown')})"  # noqa: E501
            elif param.value > c_max:
                status["valid"] = False
                status["message"] = f"Value {param.value} above constraint maximum {c_max} ({constraint.get('type', 'unknown')})"  # noqa: E501

        # Step check
        if param.step > 0:
            # Check if value aligns with step (allow small floating point tolerance)
            remainder = (param.value - param.minimum) % param.step
            if remainder > 1e-6 and abs(remainder - param.step) > 1e-6:
                status["warning"] = f"Value {param.value} not aligned with step {param.step}"

        # Evidence tier warnings (robust to use_enum_values stringification)
        tier_val = self._enum_val(param.evidence.tier)
        if tier_val in (EvidenceTier.NON_IDENTIFIABLE.value, EvidenceTier.NOT_AVAILABLE.value):
            status["warning"] = f"Parameter has {tier_val} evidence - effects uncertain"

        return status

    def _validate_cross_parameters(self, params: SetupParameters, result: ValidationResult) -> None:
        """Validate cross-parameter constraints."""
        # Rake check: rear ride height should be >= front ride height (typically)
        front_rh = params.ride_height_front.value
        rear_rh = params.ride_height_rear.value
        if rear_rh < front_rh:
            result.add_warning(f"Negative rake: rear ride height ({rear_rh}) < front ({front_rh})")

        # Aero balance: extreme front/rear wing splits can be unstable
        fw = params.front_wing.value
        rw = params.rear_wing.value
        if abs(fw - rw) > 6:
            result.add_warning(f"Large front/rear wing split: FW={fw}, RW={rw} (diff={abs(fw-rw)})")

        # Brake bias with extreme aero
        bb = params.brake_bias.value
        if bb > 60 and rw > 8:
            result.add_warning(f"High brake bias ({bb}%) with high rear wing ({rw}) may cause rear locking")  # noqa: E501

        # Camber extremes with stiff suspension
        fc = abs(params.front_camber.value)
        rc = abs(params.rear_camber.value)
        fs = params.front_spring.value
        rs = params.rear_spring.value
        if fc > 4.0 and fs < 3.0:
            result.add_warning(f"High front camber ({fc}°) with soft front spring ({fs}) may cause instability")  # noqa: E501
        if rc > 3.0 and rs < 3.0:
            result.add_warning(f"High rear camber ({rc}°) with soft rear spring ({rs}) may cause instability")  # noqa: E501

        # Tyre pressure with camber
        fp = params.tyre_pressure_front.value
        if fp < 20.0 and fc > 3.5:
            result.add_warning(f"Low front pressure ({fp} psi) with high camber ({fc}°) increases wear risk")  # noqa: E501

    def _validate_track_specific(
        self, params: SetupParameters, track_id: str, result: ValidationResult
    ) -> None:
        """Track-specific validation warnings."""
        # These are warnings, not hard constraints
        track_warnings = {
            "monaco": {
                "rear_wing": (8, "High rear wing recommended for Monaco"),
                "ride_height_front": (25, "Higher front ride height for Monaco kerbs"),
            },
            "monza": {
                "rear_wing": (3, "Low rear wing recommended for Monza"),
                "front_wing": (3, "Low front wing recommended for Monza"),
            },
            "spa": {
                "rear_wing": (4, "Medium-low rear wing for Spa"),
            },
            "singapore": {
                "rear_wing": (7, "High rear wing for Singapore"),
                "front_wing": (7, "High front wing for Singapore"),
            },
        }

        if track_id in track_warnings:
            for param_name, (rec_value, message) in track_warnings[track_id].items():
                param = getattr(params, param_name, None)
                if param and abs(param.value - rec_value) > 2:
                    result.add_warning(f"{track_id}: {message} (current: {param.value}, recommended ~{rec_value})")  # noqa: E501

    def validate_and_clamp(self, setup: SetupState) -> tuple[SetupState, ValidationResult]:
        """Validate and return clamped setup (values forced into bounds)."""
        result = self.validate(setup)

        # Create clamped copy
        clamped = setup.model_copy(deep=True)
        for name, param in clamped.parameters.get_all().items():
            param.value = param.clamp()

        clamped.compute_fingerprint()
        return clamped, result

    def get_valid_range(self, param_name: str) -> tuple[float, float] | None:
        """Get valid (min, max) range for a parameter."""
        constraint = self.constraints.get_constraint(param_name)
        if constraint:
            return (constraint.get("minimum", 0), constraint.get("maximum", 100))
        # Fall back to parameter default
        baseline = create_baseline_setup()
        param = getattr(baseline.parameters, param_name, None)
        if param:
            return (param.minimum, param.maximum)
        return None


def create_baseline_setup(
    car_id: str = "default",
    constructor_id: str = "default",
    season: str = "2024",
    track_id: str = "monaco",
    mode: str = "hypothetical",
) -> SetupState:
    """Import here to avoid circular import."""
    from app.simulation.setup.models import create_baseline_setup as _create_baseline
    from app.simulation.setup.models import SetupMode

    return _create_baseline(car_id, constructor_id, season, track_id, SetupMode(mode))
