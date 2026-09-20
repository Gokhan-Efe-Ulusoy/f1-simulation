"""Circuit model dataclasses (Phase24). Reuses Track calibration pattern."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CircuitEffect:
    circuit_id: str
    estimate: float
    se: float
    n: int
    race_count: int
    season_range: list[int]
    shrinkage_weight: float
    evidence_tier: str
    era_prior: float = 0.0
    raw: float = 0.0

@dataclass(frozen=True)
class EraEffect:
    era: str
    mean: float
    n: int
    se: float

@dataclass(frozen=True)
class CircuitModel:
    version: str
    global_baseline: float
    era_effects: dict
    circuit_effects: dict
    circuit_era_effects: dict
    shrinkage: str
    provenance_hash: str
