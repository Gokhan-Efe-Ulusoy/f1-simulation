"""Phase 22 — Historical Replay + Counterfactual Experiment Engine.

Turns the Phase 21 scenario system into a trustworthy replay /
counterfactual engine that answers "what would probably have happened if X
had been different?" — reporting simulated distribution changes under stated
model assumptions, never historical certainty.

Evidence tiers: CALIBRATED (leakage-safe calibration dataset) | LIMITED
(partial observations) | PRIOR_ONLY (model priors) | NON_IDENTIFIABLE
(cannot be identified) | NOT_TESTABLE (no mechanism in the model).
"""
from __future__ import annotations

REPLAY_MODEL_VERSION = "replay-v1.0.0"
COUNTERFACTUAL_MODEL_VERSION = "counterfactual-v1.0.0"
SENSITIVITY_MODEL_VERSION = "sensitivity-v1.0.0"

__all__ = [
    "REPLAY_MODEL_VERSION",
    "COUNTERFACTUAL_MODEL_VERSION",
    "SENSITIVITY_MODEL_VERSION",
]
