"""Provenance helpers (Phase 9A): hashing, record stamping, chain tracking."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.data.models.canonical import DataProvenance

PARSER_VERSION = "0.1.0"


def utc_now_iso() -> str:
    """Current UTC time as ISO-8601 string (metadata only, never a seed)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def hash_payload(payload: Any) -> str:
    """Stable sha256 over a JSON-serializable payload."""
    try:
        raw = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_provenance(
    source_provider: str,
    source_record_id: str = "",
    source_url: str = "",
    raw_payload: Any = None,
    confidence: float = 1.0,
    steps: list[str] | None = None,
) -> DataProvenance:
    """Create a provenance record for one imported raw record."""
    return DataProvenance(
        source_provider=source_provider,
        source_record_id=source_record_id,
        source_url=source_url,
        retrieved_at=utc_now_iso(),
        parser_version=PARSER_VERSION,
        raw_file_hash=hash_payload(raw_payload) if raw_payload is not None else "",
        confidence=confidence,
        transformation_chain=list(steps or []),
    )
