"""Security sanitization for ingestion (Phase 10 - untrusted input)."""
from __future__ import annotations

import os
import re


def sanitize_filename(name: str) -> str:
    """Sanitize filename: prevent path traversal and formula injection."""
    # Remove path components
    name = os.path.basename(name)
    # Replace unsafe chars
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Prevent Excel formula injection
    if name and name[0] in ("=", "+", "-", "@", "|", "%"):
        name = "_" + name
    # Limit length
    return name[:200] if name else "unnamed"


def sanitize_path(path: str, base_dir: str) -> str:
    """Sanitize dataset path: prevent traversal, ensure within base_dir."""
    # Normalize
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized):
        raise ValueError(f"absolute path not allowed: {path}")
    # Check for traversal attempts
    parts = normalized.split(os.sep)
    if ".." in parts:
        raise ValueError(f"path traversal not allowed: {path}")
    for part in parts:
        if part and part[0] in ("=", "+", "-", "@"):
            raise ValueError(f"formula injection in path: {part}")
    full = os.path.join(base_dir, normalized)
    # Ensure final path is within base_dir
    abs_base = os.path.abspath(base_dir)
    abs_full = os.path.abspath(full)
    if not abs_full.startswith(abs_base):
        raise ValueError(f"path escapes base_dir: {path}")
    return full


def sanitize_csv_value(value: str) -> str:
    """Sanitize CSV cell value against formula injection."""
    if value and value[0] in ("=", "+", "-", "@", "|", "%"):
        return "'" + value
    return value


def validate_payload_size(payload: bytes, max_bytes: int = 50 * 1024 * 1024) -> None:
    """Check payload size to prevent oversized payloads."""
    if len(payload) > max_bytes:
        raise ValueError(f"payload too large: {len(payload)} > {max_bytes}")


def validate_record_count(count: int, max_records: int = 100000) -> None:
    """Check record count to prevent excessive records."""
    if count > max_records:
        raise ValueError(f"too many records: {count} > {max_records}")
