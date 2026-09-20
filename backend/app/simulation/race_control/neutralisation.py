"""Neutralisation factors and gap dynamics — PRIOR_ONLY coefficients."""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from app.simulation.race_control.models import EvidenceTier, RaceControlState


class NeutralisationFactors(BaseModel):
    """Structured pace/strategy modifiers per race-control state."""

    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    # pace_control_factor multiplies lap time? >1 slower, 1.0 normal (but we expose pace_factor for lap delta)
    pace_control_factor: float = 1.0
    overtaking_factor: float = 1.0
    battle_factor: float = 1.0
    incident_factor: float = 1.0
    pit_cost_factor: float = 1.0  # strategic opportunity cost multiplier (<1 cheaper under SC)
    drs_enabled: bool = True

    model_config = {"use_enum_values": True}


# PRIOR_ONLY table — documented as assumptions, not calibrated.
NEUTRALISATION_TABLE: dict[RaceControlState, NeutralisationFactors] = {
    RaceControlState.GREEN: NeutralisationFactors(
        pace_control_factor=1.0, overtaking_factor=1.0, battle_factor=1.0, incident_factor=1.0, pit_cost_factor=1.0, drs_enabled=True, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.YELLOW: NeutralisationFactors(
        pace_control_factor=1.15, overtaking_factor=0.25, battle_factor=0.35, incident_factor=0.85, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.DOUBLE_YELLOW: NeutralisationFactors(
        pace_control_factor=1.22, overtaking_factor=0.1, battle_factor=0.2, incident_factor=0.75, pit_cost_factor=0.95, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.VSC: NeutralisationFactors(
        pace_control_factor=1.30, overtaking_factor=0.05, battle_factor=0.1, incident_factor=0.65, pit_cost_factor=0.55, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.SAFETY_CAR: NeutralisationFactors(
        pace_control_factor=1.40, overtaking_factor=0.0, battle_factor=0.0, incident_factor=0.50, pit_cost_factor=0.35, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.RED_FLAG: NeutralisationFactors(
        pace_control_factor=0.0, overtaking_factor=0.0, battle_factor=0.0, incident_factor=0.0, pit_cost_factor=0.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.RACE_SUSPENDED: NeutralisationFactors(
        pace_control_factor=0.0, overtaking_factor=0.0, battle_factor=0.0, incident_factor=0.0, pit_cost_factor=0.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.RESTART: NeutralisationFactors(
        pace_control_factor=1.05, overtaking_factor=1.35, battle_factor=1.25, incident_factor=1.15, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.FORMATION_LAP: NeutralisationFactors(
        pace_control_factor=1.45, overtaking_factor=0.0, battle_factor=0.0, incident_factor=0.9, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.START: NeutralisationFactors(
        pace_control_factor=1.0, overtaking_factor=1.2, battle_factor=1.1, incident_factor=2.0, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.RACE_RESUMED: NeutralisationFactors(
        pace_control_factor=1.05, overtaking_factor=1.25, battle_factor=1.15, incident_factor=1.1, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
    RaceControlState.CHEQUERED_FLAG: NeutralisationFactors(
        pace_control_factor=0.0, overtaking_factor=0.0, battle_factor=0.0, incident_factor=0.0, pit_cost_factor=1.0, drs_enabled=False, evidence_tier=EvidenceTier.PRIOR_ONLY  # noqa: E501
    ),
}


def factors_for(state: RaceControlState) -> NeutralisationFactors:
    return NEUTRALISATION_TABLE.get(state, NEUTRALISATION_TABLE[RaceControlState.GREEN])


# ---------------------------------------------------------------------------
# Gap dynamics — field compression under SC/VSC
# ---------------------------------------------------------------------------
def compress_gaps_step(
    gaps: np.ndarray,  # (N,D) or (N,) gap_to_ahead in seconds (>=0)
    mask_neutralised: np.ndarray,  # (N,) bool: this sim is under SC/VSC
    mode: str = "safety_car",
    target_gap: float = 0.7,  # seconds
    rate: float = 0.55,  # per lap convergence (0-1)
) -> np.ndarray:
    """Progressive gap compression: gap -> target with rate, no teleport.

    For VSC, rate smaller (less compression). For SC, faster.
    Ensures gap >=0, preserves order (no overtaking injected).
    """
    out = gaps.copy()
    if mode == "safety_car":
        r = rate
    elif mode == "vsc":
        r = rate * 0.45
    else:
        r = rate
    # Only where neutralised
    # gaps currently per-driver gap_ahead (leader 0)
    # We compress towards target: new = old*(1-r) + target*r  but leader stays 0
    # For leader gap=0, this would move to target*r -> wrong, so keep leader fixed.
    # Detect leader: gap==0 is leader; leave at 0.
    leader_mask = gaps == 0.0
    compress = mask_neutralised[:, None] if gaps.ndim == 2 else mask_neutralised
    # For 2D case
    if gaps.ndim == 2:
        # expand mask to (N,D)
        cm = np.repeat(compress, gaps.shape[1], axis=1) if compress.ndim == 2 else np.broadcast_to(compress[:, None], gaps.shape)  # noqa: E501
        new = gaps * (1 - r) + target_gap * r
        # keep leaders 0
        new = np.where(leader_mask, 0.0, new)
        out = np.where(cm, new, gaps)
        # Ensure non-negative, and leader 0
        out = np.maximum(0.0, out)
    else:
        new = gaps * (1 - r) + target_gap * r
        new = np.where(leader_mask, 0.0, new)
        out = np.where(compress, new, gaps)
        out = np.maximum(0.0, out)
    return out


def apply_pace_control(
    lap_times: np.ndarray,  # (N,D)
    race_state_per_sim: np.ndarray,  # (N,) int phase enum value or (N,D)? We'll use (N,) shared
    factor_map: dict[int, float] | None = None,
) -> np.ndarray:
    """Apply lap-time pace scaling per race-control state (vectorized)."""
    if factor_map is None:
        # map from int to pace factor
        factor_map = {
            0: 1.0,   # GREEN
            1: 1.15,  # YELLOW
            2: 1.22,  # DOUBLE_YELLOW
            3: 1.30,  # VSC
            4: 1.40,  # SC
            5: 0.0,   # RED_FLAG -> times frozen? we set to 0 delta later
        }
    # This is a no-op in new path: we handle SC pace via separate kernel override
    return lap_times
