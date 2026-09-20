"""Phase 20 — Car Setup & Vehicle Configuration Engine.

Provides structured representation of car configuration and its effects
on vehicle characteristics, lap time, tyre degradation, and race dynamics.
"""
from __future__ import annotations

from app.simulation.setup.models import (
    SetupState,
    SetupParameters,
    SetupConstraints,
    SetupEffects,
    SetupEvidence,
    EvidenceTier,
    ConstraintType,
    SetupMode,
)
from app.simulation.setup.engine import SetupEngine
from app.simulation.setup.validator import SetupValidator
from app.simulation.setup.fingerprint import setup_fingerprint

__all__ = [
    "SetupState",
    "SetupParameters",
    "SetupConstraints",
    "SetupEffects",
    "SetupEvidence",
    "EvidenceTier",
    "ConstraintType",
    "SetupMode",
    "SetupEngine",
    "SetupValidator",
    "setup_fingerprint",
]

# Version
SETUP_MODEL_VERSION = "setup-v1.0.0"
