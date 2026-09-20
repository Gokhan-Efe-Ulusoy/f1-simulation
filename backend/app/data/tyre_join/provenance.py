"""Provenance."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone

def make_provenance(source_record_id: str, raw_sha256: str):
    return {"source_record_id": source_record_id, "raw_sha256": raw_sha256, "retrieved_at": datetime.now(timezone.utc).isoformat()}  # noqa: E501
