"""Baseline lap-time hierarchical calculation."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).parents[3]
MODEL_JSON=ROOT/"data/calibration/phase24/circuit_model.json"

def load_circuit_model():
    with open(MODEL_JSON) as f:
        return json.load(f)

def predict_lap_time(circuit_id: str, season: int, global_only: bool=False):
    m=load_circuit_model()
    base=m["global_baseline"]
    if global_only:
        return base
    ce=m["circuit_effects"].get(circuit_id, {}).get("estimate", 0)
    return base + ce
