"""Circuit descriptors - only observed values, null+available=false if unavailable."""
from __future__ import annotations
import json, os
from pathlib import Path

ROOT=Path(__file__).parents[3]
CIRCUITS_JSON=ROOT/"data/canonical/circuits.json"

def load_descriptors():
    # Only reuse existing circuits.json, no invented descriptors
    if not CIRCUITS_JSON.exists():
        return {}
    with open(CIRCUITS_JSON) as f:
        circuits=json.load(f)
    # Build minimal descriptor map: circuit_id -> {length, type, etc if available}
    descs={}
    for c in circuits:
        cid=c.get("circuitId") or c.get("circuit_id") or c.get("id")
        # Only include reliably available fields
        descs[cid]={
            "circuit_id": cid,
            "name": c.get("name") or c.get("circuitName",""),
            "available": True,
            "evidence_tier": "OBSERVABLE",
            # layout generation, race distance etc would be derived from races.json lap distance if available, else null
            "lap_distance": None,
            "race_distance": None,
            "available_fields": list(c.keys())
        }
    return descs
