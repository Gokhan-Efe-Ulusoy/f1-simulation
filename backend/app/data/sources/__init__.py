"""Source adapters (Phase 9B). Each adapter emits source-specific raw records."""
from __future__ import annotations

from app.data.sources.base import RawBundle, SourceAdapter
from app.data.sources.csv_adapter import OfficialCsvAdapter
from app.data.sources.fastf1_adapter import FastF1Adapter
from app.data.sources.jolpica import JolpicaAdapter

__all__ = [
    "RawBundle",
    "SourceAdapter",
    "OfficialCsvAdapter",
    "FastF1Adapter",
    "JolpicaAdapter",
]
