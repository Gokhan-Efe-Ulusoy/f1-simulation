"""Tyre state for Phase 16 — stateful, deterministic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.simulation.tyre.compound import CanonicalCompound
from app.simulation.tyre.tyre_era import TyreEra

@dataclass
class TyreState:
    compound: CanonicalCompound | None = None
    source_compound: str | None = None
    tyre_era: TyreEra = TyreEra.HISTORICAL
    tyre_age: int | None = None  # laps since stint start, None if unavailable
    stint_index: int = 0
    start_lap: int | None = None
    grip: float = 1.0  # 0-1, 1 = optimal
    degradation: float = 0.0  # seconds per lap effect
    warmup: float = 0.0  # warmup penalty
    available: bool = False
    evidence_tier: str = "NON_IDENTIFIABLE"

    def is_available(self) -> bool:
        return self.available and self.compound is not None and self.tyre_age is not None
