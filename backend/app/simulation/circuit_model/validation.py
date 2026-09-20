"""Validation helpers."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).parents[3]
WF=ROOT/"data/calibration/phase24/walk_forward.json"
def load_walk_forward():
    with open(WF) as f:
        return json.load(f)
