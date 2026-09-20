"""Ingestion manifests: reproducible run records (Phase 9B)."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.data.provenance import hash_payload, utc_now_iso


class IngestionManifest(BaseModel):
    """One ingestion run record (serializable, append-only on disk)."""

    run_id: str
    source: str
    started_at: str = ""
    completed_at: str = ""
    coverage: str = ""
    records_fetched: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    warnings: list[str] = Field(default_factory=list)
    parser_version: str = "0.1.0"
    schema_version: str = "0.1.0"
    payload_hash: str = ""

    model_config = {"use_enum_values": True}


def run_ingestion(
    root: str,
    source: str,
    coverage: str,
    bundles: list[Any],
    parser_version: str = "0.1.0",
    schema_version: str = "0.1.0",
    run_id: str | None = None,
) -> IngestionManifest:
    """Build + persist a manifest for already-fetched bundles.

    Fetching stays in adapters (testable without I/O); this function only
    records what happened. Raw bundles are stored under data/raw/<source>/.
    """
    started = utc_now_iso()
    fetched = sum(len(getattr(b, "records", [])) for b in bundles)
    rejected_items: list[str] = []
    warnings: list[str] = []
    for bundle in bundles:
        rejected_items.extend(getattr(bundle, "rejected", []))
        warnings.extend(getattr(bundle, "warnings", []))
    accepted = fetched  # bundles carry accepted records; rejected counted separately
    manifest = IngestionManifest(
        run_id=run_id or uuid.uuid4().hex,
        source=source,
        started_at=started,
        completed_at=utc_now_iso(),
        coverage=coverage,
        records_fetched=fetched,
        records_accepted=accepted,
        records_rejected=len(rejected_items),
        warnings=warnings + rejected_items,
        parser_version=parser_version,
        schema_version=schema_version,
        payload_hash=hash_payload([getattr(b, "records", []) for b in bundles]),
    )
    directory = os.path.join(root, "data", "manifests")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{manifest.run_id}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest.model_dump(), handle, indent=2, sort_keys=True)
    raw_dir = os.path.join(root, "data", "raw", source)
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{manifest.run_id}.json")
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump([getattr(b, "records", []) for b in bundles], handle, indent=2)
    return manifest
