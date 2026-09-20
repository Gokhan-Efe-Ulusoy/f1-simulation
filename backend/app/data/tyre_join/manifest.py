"""Manifest helpers."""
from __future__ import annotations
import json, hashlib
from pathlib import Path

def hash_manifest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]
