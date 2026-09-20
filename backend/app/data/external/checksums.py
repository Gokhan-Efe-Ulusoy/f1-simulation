"""SHA-256 integrity helpers (Phase 22.5).

Every raw payload gets a sidecar with hash + provenance so downstream
stages can verify immutability before use.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """Hex SHA-256 of a file (streamed)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sidecar(
    data_path: str,
    *,
    source_id: str,
    source_url: str,
    license: str,
    download_timestamp: str,
    source_version: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write `<data_path>.provenance.json` and return its content."""
    payload: dict[str, Any] = {
        "source_id": source_id,
        "source_url": source_url,
        "source_version": source_version,
        "license": license,
        "download_timestamp": download_timestamp,
        "file_size": os.path.getsize(data_path),
        "sha256": sha256_file(data_path),
    }
    if extra:
        payload.update(extra)
    sidecar = data_path + ".provenance.json"
    with open(sidecar, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return payload


def verify_sidecar(data_path: str) -> tuple[bool, str]:
    """Re-hash a raw file against its sidecar. Returns (ok, reason)."""
    sidecar = data_path + ".provenance.json"
    if not os.path.exists(sidecar):
        return False, "missing sidecar"
    with open(sidecar, encoding="utf-8") as handle:
        meta = json.load(handle)
    expected = str(meta.get("sha256", ""))
    if not expected:
        return False, "sidecar has no sha256"
    actual = sha256_file(data_path)
    if actual != expected:
        return False, f"hash mismatch: {actual[:16]} != {expected[:16]}"
    return True, "ok"
