"""Race control policy — configuration-driven, evidence-tier aware.

Maps incident severity / weather assessment -> race-control response.
All thresholds are prior-only; no empirical calibration claimed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from app.simulation.race_control.models import EvidenceTier, IncidentSeverity, RaceControlState


class RaceControlDecision(str, Enum):
    NO_ACTION = "NO_ACTION"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    VSC = "VSC"
    SAFETY_CAR = "SAFETY_CAR"
    RED_FLAG = "RED_FLAG"


@dataclass
class IncidentAssessment:
    severity: IncidentSeverity
    is_retirement: bool = False
    causes_blockage: bool = False
    requires_marshal: bool = False


class RaceControlPolicy(BaseModel):
    """Thresholds mapping severity -> race-control action.

    PRIOR_ONLY — not empirically calibrated.
    """

    # Severity -> decision (configuration-driven)
    minor_action: RaceControlDecision = RaceControlDecision.NO_ACTION
    moderate_action: RaceControlDecision = RaceControlDecision.YELLOW
    major_action: RaceControlDecision = RaceControlDecision.SAFETY_CAR
    severe_action: RaceControlDecision = RaceControlDecision.RED_FLAG

    # Probabilities that a given severity escalates to next tier (prior)
    vsc_probability_major: float = Field(default=0.35, ge=0, le=1)
    sc_probability_major: float = Field(default=0.50, ge=0, le=1)
    red_flag_probability_severe: float = Field(default=0.40, ge=0, le=1)

    # Weather thresholds for escalation (prior)
    wetness_red_flag_threshold: float = Field(default=0.85, ge=0, le=1)
    rainfall_red_flag_threshold_mm_h: float = Field(default=15.0, ge=0, le=100)
    visibility_red_flag_threshold_km: float = Field(default=0.5, ge=0, le=20)
    consecutive_wet_laps_for_red: int = Field(default=3, ge=1, le=10)

    # Duration priors (laps)
    yellow_duration_laps: int = Field(default=1, ge=1, le=5)
    double_yellow_duration_laps: int = Field(default=1, ge=1, le=5)
    vsc_duration_laps: tuple[int, int] = Field(default=(2, 4))
    sc_duration_laps: tuple[int, int] = Field(default=(3, 6))
    red_flag_duration_laps: tuple[int, int] = Field(default=(3, 6))

    # First-lap / start multipliers (prior)
    start_incident_multiplier: float = Field(default=3.0, ge=1, le=10)
    first_lap_density_multiplier: float = Field(default=2.0, ge=1, le=10)
    first_corner_risk: float = Field(default=0.02, ge=0, le=0.2)

    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY

    model_config = {"use_enum_values": True}

    def decide_for_incident(self, assessment: IncidentAssessment, rng) -> RaceControlDecision:
        """Deterministic mapping severity -> decision with stochastic escalation."""
        s = assessment.severity
        if s == IncidentSeverity.MINOR:
            return self.minor_action
        if s == IncidentSeverity.MODERATE:
            # moderate -> YELLOW normally, but if blockage escalate to DOUBLE_YELLOW
            if assessment.causes_blockage and rng.random() < 0.3:
                return RaceControlDecision.DOUBLE_YELLOW
            return RaceControlDecision.YELLOW
        if s == IncidentSeverity.MAJOR:
            roll = rng.random()
            if assessment.is_retirement and roll < self.sc_probability_major:
                return RaceControlDecision.SAFETY_CAR
            if roll < self.vsc_probability_major:
                return RaceControlDecision.VSC
            # fallback double yellow
            return RaceControlDecision.DOUBLE_YELLOW
        if s == IncidentSeverity.SEVERE:
            if assessment.causes_blockage or assessment.is_retirement:
                if rng.random() < self.red_flag_probability_severe:
                    return RaceControlDecision.RED_FLAG
                return RaceControlDecision.SAFETY_CAR
            return RaceControlDecision.SAFETY_CAR
        return RaceControlDecision.NO_ACTION

    def decide_for_weather(
        self, rainfall_mm_h: float, wetness: float, visibility_km: float | None, consecutive_wet_laps: int  # noqa: E501
    ) -> RaceControlDecision:
        """Policy: extreme weather -> RED_FLAG, heavy rain -> SAFETY_CAR/VSC."""
        if rainfall_mm_h >= self.rainfall_red_flag_threshold_mm_h and wetness >= self.wetness_red_flag_threshold:  # noqa: E501
            if consecutive_wet_laps >= self.consecutive_wet_laps_for_red:
                return RaceControlDecision.RED_FLAG
            return RaceControlDecision.SAFETY_CAR
        if wetness >= 0.7 and rainfall_mm_h >= 7.5:
            return RaceControlDecision.SAFETY_CAR
        if wetness >= 0.5 and rainfall_mm_h >= 2.5:
            return RaceControlDecision.VSC
        if visibility_km is not None and visibility_km <= self.visibility_red_flag_threshold_km:
            return RaceControlDecision.RED_FLAG
        return RaceControlDecision.NO_ACTION


# Default prior policy
DEFAULT_RACE_CONTROL_POLICY = RaceControlPolicy()
