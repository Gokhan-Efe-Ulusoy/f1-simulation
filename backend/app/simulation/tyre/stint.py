"""Canonical tyre-stint models for Phase 16."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

class TyreStint(BaseModel):
    season: int
    race_id: str
    driver_id: str
    stint_index: int
    compound: str | None = None  # canonical
    source_compound: str | None = None
    tyre_era: str
    start_lap: int | None = None
    end_lap: int | None = None
    lap_count: int | None = None
    source: str  # f1db, openf1, fastf1, jolpica
    source_record_id: str = ""
    provenance_hash: str = ""
    dataset_version: str = "f1-dataset-v1.1"
    available: bool = True
    evidence_tier: str = "OBSERVED"  # OBSERVED, CALIBRATED, LIMITED, PRIOR_ONLY, NON_IDENTIFIABLE
    sample_size: int = 1

    model_config = {"use_enum_values": True}

class TyreLapObservation(BaseModel):
    season: int
    race_id: str
    driver_id: str
    lap: int
    stint_index: int | None = None
    compound: str | None = None
    tyre_age: int | None = None
    lap_time: float | None = None
    source: str
    timestamp: str = ""
    provenance_hash: str = ""

    model_config = {"use_enum_values": True}
