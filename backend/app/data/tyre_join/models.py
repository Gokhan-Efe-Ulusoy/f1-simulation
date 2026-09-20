"""Tyre join models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class JoinedLap:
    race_id: str
    season: int
    driver_number: int
    lap_number: int
    stint_id: str
    compound: Optional[str]
    tyre_age: Optional[int]
    stint_lap: Optional[int]
    join_confidence: str  # EXACT, DETERMINISTIC, AMBIGUOUS, UNJOINED
    evidence_tier: str
    source_reference: str
