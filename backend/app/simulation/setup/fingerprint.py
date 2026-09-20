"""Phase 20 — Setup fingerprinting for deterministic reproducibility."""
from __future__ import annotations

import hashlib
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.setup.models import SetupState


def setup_fingerprint(setup: SetupState) -> str:  # type: ignore[valid-type]
    """Compute deterministic fingerprint of a setup configuration.

    The fingerprint includes:
    - All parameter values
    - Model version
    - Setup mode
    - Car/track/season context

    Does NOT include: timestamps, random seeds, provenance metadata that varies.
    """
    # Build stable payload
    payload = {
        "model_version": setup.model_version,
        "setup_id": setup.setup_id,
        "car_id": setup.car_id,
        "constructor_id": setup.constructor_id,
        "season": setup.season,
        "track_id": setup.track_id,
        "mode": setup.mode.value if hasattr(setup.mode, "value") else str(setup.mode),
        "parameters": setup.parameters.get_values(),
    }

    # Stable JSON serialization
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def setup_fingerprint_full(setup: SetupState) -> str:  # type: ignore[valid-type]
    """Compute full fingerprint including effects and evidence (for debugging)."""
    payload = {
        "model_version": setup.model_version,
        "setup_id": setup.setup_id,
        "car_id": setup.car_id,
        "constructor_id": setup.constructor_id,
        "season": setup.season,
        "track_id": setup.track_id,
        "mode": setup.mode.value if hasattr(setup.mode, "value") else str(setup.mode),
        "parameters": setup.parameters.get_values(),
        "effects": setup.effects.model_dump() if setup.effects else None,
        "evidence": setup.evidence.model_dump() if setup.evidence else None,
    }

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scenario_fingerprint(scenario: dict[str, Any], setup: SetupState | None = None) -> str:  # type: ignore[valid-type]  # noqa: E501
    """Compute fingerprint for a scenario including setup."""
    payload = {
        "scenario": {k: v for k, v in scenario.items() if k not in ("provenance", "timestamp")},
    }
    if setup:
        payload["setup"] = {
            "setup_id": setup.setup_id,
            "parameters": setup.parameters.get_values(),
            "fingerprint": setup.fingerprint,
        }

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def verify_fingerprint(setup: SetupState, expected: str) -> bool:  # type: ignore[valid-type]
    """Verify setup fingerprint matches expected value."""
    actual = setup_fingerprint(setup)
    return actual == expected
