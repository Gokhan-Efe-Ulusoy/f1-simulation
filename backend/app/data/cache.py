"""Ingestion cache: content-hashed, keyed by source+endpoint+params (Phase 10B).

Avoids unnecessary network requests; cache is file-based under
data/raw/.cache/ with sanitized filenames. Raw immutability is preserved:
cache entries are never overwritten, only new versions are added.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from app.data.provenance import hash_payload


def _sanitize_filename(name: str) -> str:
    """Sanitize a filename: no path traversal, no formula injection."""
    # Prevent path traversal and formula injection
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Prevent Excel formula injection
    if name and name[0] in ("=", "+", "-", "@"):
        name = "_" + name
    return name[:200]


def cache_key(source: str, endpoint: str, params: dict[str, Any] | None = None,
              source_version: str | None = None) -> str:
    """Deterministic cache key from request identity."""
    payload = {
        "source": source,
        "endpoint": endpoint,
        "params": params or {},
        "source_version": source_version or "",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


class IngestionCache:
    """File-based cache for raw ingestion. Offline-first: tests run without network."""

    def __init__(self, root: str = "data/raw/.cache") -> None:
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def _path_for(self, key: str) -> str:
        return os.path.join(self.root, f"{_sanitize_filename(key)}.json")

    def get(self, source: str, endpoint: str, params: dict[str, Any] | None = None,
            source_version: str | None = None) -> dict[str, Any] | None:
        """Return cached payload or None."""
        key = cache_key(source, endpoint, params, source_version)
        path = self._path_for(key)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def put(self, source: str, endpoint: str, payload: Any,
            params: dict[str, Any] | None = None,
            source_version: str | None = None) -> str:
        """Cache a payload; returns content hash."""
        key = cache_key(source, endpoint, params, source_version)
        path = self._path_for(key)
        content_hash = hash_payload(payload)
        data = {"payload": payload, "content_hash": content_hash,
                "source": source, "endpoint": endpoint}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        return content_hash

    def has(self, source: str, endpoint: str, params: dict[str, Any] | None = None,
            source_version: str | None = None) -> bool:
        """Check cache existence without loading."""
        key = cache_key(source, endpoint, params, source_version)
        return os.path.exists(self._path_for(key))
