"""Dataset versioning (Phase 9A): immutable version records + registry."""
from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"


class DatasetVersion(BaseModel):
    """Immutable metadata record for one dataset build (frozen)."""

    model_config = {"frozen": True, "use_enum_values": True}

    dataset_id: str = Field(description="e.g. 'f1-dataset-v0.1.0'")
    schema_version: str = SCHEMA_VERSION
    source_versions: dict[str, str] = Field(default_factory=dict)
    extraction_date: str = ""
    coverage: dict[str, Any] = Field(default_factory=dict)
    record_counts: dict[str, int] = Field(default_factory=dict)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    known_limitations: list[str] = Field(default_factory=list)


def registry_path(root: str) -> str:
    """Path of the append-only dataset registry file."""
    return os.path.join(root, "data", "manifests", "registry.json")


def register_version(root: str, version: DatasetVersion) -> DatasetVersion:
    """Append a version record; never mutate existing entries."""
    path = registry_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entries: list[dict[str, Any]] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            entries = json.load(handle)
    if any(e.get("dataset_id") == version.dataset_id for e in entries):
        raise ValueError(f"dataset version already registered: {version.dataset_id}")
    entries.append(version.model_dump())
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2, sort_keys=True)
    return version


def list_versions(root: str) -> list[DatasetVersion]:
    """List registered versions in registration order."""
    path = registry_path(root)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [DatasetVersion(**entry) for entry in json.load(handle)]
