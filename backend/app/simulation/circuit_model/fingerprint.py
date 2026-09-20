"""Fingerprint - dataset, model version, config, hashes."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).parents[3]
def fingerprint():
    with open(ROOT/"data/calibration/phase24/fingerprint.json") as f:
        return json.load(f)
def deterministic_hash():
    fp=fingerprint()
    return hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:8]
