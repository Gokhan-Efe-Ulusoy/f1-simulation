"""Data promotion gate (Phase 22.5).

External data NEVER becomes authoritative automatically. For every variable
the gate records current_status, new observations, coverage delta, source
quality, conflict rate, missingness, temporal resolution and an explicit
promotion_candidate flag. Promotion requires evidence; era relabeling is
scoped to the eras actually observed.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromotionAssessment(BaseModel):
    """Gate verdict for one variable."""

    variable: str = ""
    current_status: str = ""
    new_observations: int = 0
    coverage_delta: str = ""
    source_quality: str = ""
    conflict_rate: float = 0.0
    missingness: float = 1.0
    temporal_resolution: str = ""
    promotion_candidate: bool = False
    promoted_tier: str = ""
    reason: str = ""

    model_config = {"use_enum_values": True}


# Conflict-rate ceiling above which promotion is refused (data disagree).
_MAX_CONFLICT_RATE = 0.05


def assess_promotion(
    *,
    variable: str,
    current_status: str,
    new_observations: int,
    eras_observed: list[str],
    eras_claimed: list[str],
    source_ids: list[str],
    conflicts: int,
    compared: int,
    missingness: float,
    temporal_resolution: str,
    min_observations: int = 100,
) -> PromotionAssessment:
    """Evaluate one variable against the promotion policy.

    Policy: promote only when (a) observations exist, (b) conflict rate is
    low, (c) missingness < 50%, (d) observed eras cover the claimed eras.
    The promoted tier never exceeds LIMITED for staged (non-canonical) data.
    """
    conflict_rate = (conflicts / compared) if compared > 0 else 0.0
    unobserved = [e for e in eras_claimed if e not in eras_observed]
    if new_observations < min_observations:
        return PromotionAssessment(
            variable=variable, current_status=current_status,
            new_observations=new_observations,
            coverage_delta=f"eras observed: {eras_observed}",
            source_quality=",".join(source_ids), conflict_rate=conflict_rate,
            missingness=missingness, temporal_resolution=temporal_resolution,
            promotion_candidate=False, promoted_tier=current_status,
            reason=f"insufficient observations ({new_observations} < {min_observations})",
        )
    if conflict_rate > _MAX_CONFLICT_RATE:
        return PromotionAssessment(
            variable=variable, current_status=current_status,
            new_observations=new_observations,
            coverage_delta=f"eras observed: {eras_observed}",
            source_quality=",".join(source_ids), conflict_rate=conflict_rate,
            missingness=missingness, temporal_resolution=temporal_resolution,
            promotion_candidate=False, promoted_tier=current_status,
            reason=f"conflict rate {conflict_rate:.3f} exceeds {_MAX_CONFLICT_RATE}",
        )
    if missingness >= 0.5:
        return PromotionAssessment(
            variable=variable, current_status=current_status,
            new_observations=new_observations,
            coverage_delta=f"eras observed: {eras_observed}",
            source_quality=",".join(source_ids), conflict_rate=conflict_rate,
            missingness=missingness, temporal_resolution=temporal_resolution,
            promotion_candidate=False, promoted_tier=current_status,
            reason=f"missingness {missingness:.2f} too high",
        )
    if unobserved:
        return PromotionAssessment(
            variable=variable, current_status=current_status,
            new_observations=new_observations,
            coverage_delta=f"observed {eras_observed}; NOT observed {unobserved} — no relabel there",  # noqa: E501
            source_quality=",".join(source_ids), conflict_rate=conflict_rate,
            missingness=missingness, temporal_resolution=temporal_resolution,
            promotion_candidate=True, promoted_tier="LIMITED",
            reason=(f"candidate for LIMITED in observed eras only ({eras_observed}); "
                    f"eras {unobserved} keep {current_status}"),
        )
    return PromotionAssessment(
        variable=variable, current_status=current_status,
        new_observations=new_observations,
        coverage_delta=f"eras observed: {eras_observed}",
        source_quality=",".join(source_ids), conflict_rate=conflict_rate,
        missingness=missingness, temporal_resolution=temporal_resolution,
        promotion_candidate=True, promoted_tier="LIMITED",
        reason="meets observation/conflict/missingness bars; staged as LIMITED candidate",
    )


def assessments_to_json(items: list[PromotionAssessment]) -> list[dict[str, Any]]:
    """Serializable gate snapshot."""
    return [a.model_dump() for a in items]
