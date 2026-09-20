"""Deterministic resolver for lap->stint using race_id+driver_number+lap_number."""
from __future__ import annotations
import math
from typing import List, Dict

def resolve_lap(lap: dict, stints: List[Dict]) -> tuple[str, dict]:
    """Resolve single lap to stint. Returns (confidence, match)."""
    ln=lap["lap_number"]
    matches=[s for s in stints if s["lap_start"] <= ln <= s["lap_end"]]
    if len(matches)==1:
        return "EXACT", matches[0]
    if len(matches)==0:
        return "UNJOINED", {}
    return "AMBIGUOUS", {}
