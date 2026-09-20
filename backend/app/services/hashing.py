"""Phase 29 — Request / result hashing (deterministic, no timestamps)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, no whitespace variance."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def request_hash(
    race_id: str,
    simulation_type: str,
    seed: int | None,
    sample_count: int | None = None,
    laps: int | None = None,
    modifiers: dict[str, Any] | None = None,
    interventions: list[dict[str, Any]] | None = None,
    engine_version: str | None = None,
    model_version: str | None = None,
    dataset_version: str | None = None,
) -> str:
    """Canonical request fingerprint (excludes timestamps, ids, paths)."""
    payload: dict[str, Any] = {
        "race_id": str(race_id),
        "simulation_type": str(simulation_type),
        "seed": seed,
        "sample_count": sample_count,
        "laps": laps,
        "modifiers": modifiers or {},
        "interventions": interventions or [],
        "engine_version": engine_version or "",
        "model_version": model_version or "",
        "dataset_version": dataset_version or "",
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]


def result_hash(result: Any) -> str:
    """Hash of normalized result content (excludes timestamps)."""
    try:
        data = result if isinstance(result, dict) else {"result": str(result)}
        # remove transient keys
        data = {k: v for k, v in dict(data).items() if k not in ("created_at", "updated_at", "execution_time")}  # noqa: E501
        return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(str(result).encode("utf-8")).hexdigest()[:16]
