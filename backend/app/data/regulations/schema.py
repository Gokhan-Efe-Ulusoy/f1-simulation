"""Regulation evidence schema (Phase 22.5).

One row = one (season, category, parameter) fact with effective date,
source citation and confidence. The simulation must NOT read coefficients
from here; a later phase may propose a mapping with its own review.
"""
from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

REGULATION_CATEGORIES: list[str] = [
    "DRS_ALLOWED",
    "MIN_WEIGHT",
    "FUEL_FLOW_LIMIT",
    "TYRE_RULE",
    "QUALIFYING_FORMAT",
    "POINTS_SYSTEM",
    "ENGINE_FORMULA",
    "AERO_REGULATION",
    "SPRINT_FORMAT",
    "REFUELLING",
    "PARC_FERME",
    "FASTEST_LAP_POINT",
]


class RegulationParameter(BaseModel):
    """One documented regulation fact (evidence, not a coefficient)."""

    era: str = ""
    season: int = Field(ge=1950, le=2026)
    regulation_category: str = ""
    parameter: str = ""
    value: str = ""
    unit: str = ""
    effective_date: str = ""
    source: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = {"use_enum_values": True}


def _seed() -> list[RegulationParameter]:
    rows: list[RegulationParameter] = []

    def add(season: int, cat: str, param: str, value: str, conf: float,
            unit: str = "", date: str = "", source: str = "FIA documents (curated extraction)") -> None:  # noqa: E501
        era = "modern-hybrid" if season >= 2014 else ("v8-kers" if season >= 2009 else "pre-2009")
        rows.append(RegulationParameter(
            era=era, season=season, regulation_category=cat, parameter=param,
            value=value, unit=unit, effective_date=date or f"{season}-01-01",
            source=source, confidence=conf))

    for year in range(1950, 2027):
        add(year, "REFUELLING", "refuelling_allowed",
            "yes" if year <= 2009 else "no", 0.9 if year <= 2009 else 0.95)
        add(year, "DRS_ALLOWED", "drs_permitted",
            "yes" if year >= 2011 else "no", 0.95 if year >= 2011 else 0.9)
        add(year, "SPRINT_FORMAT", "sprint_weekends_exist",
            "yes" if year >= 2021 else "no", 0.9)
        add(year, "POINTS_SYSTEM", "points_positions",
            "10 (25-18-15-12-10-8-6-4-2-1)" if year >= 2010 else "pre-2010 system (not encoded)",
            0.95 if year >= 2010 else 0.6)
        if 2019 <= year <= 2024:
            add(year, "FASTEST_LAP_POINT", "fastest_lap_point_awarded", "yes", 0.8)
    add(2024, "MIN_WEIGHT", "minimum_weight", "798", 0.9, unit="kg",
        date="2024-01-01", source="FIA Technical Regulations Art 4.1 (curated extraction)")
    add(2024, "FUEL_FLOW_LIMIT", "max_fuel_flow", "100", 0.9, unit="kg/h",
        date="2024-01-01", source="FIA Technical Regulations Art 5.4 (curated extraction)")
    add(2024, "TYRE_RULE", "dry_compounds_per_weekend", "3 (C1-C5 range, 2 mandatory)", 0.85,
        source="FIA Sporting Regulations + Pirelli allocation (curated extraction)")
    add(2024, "QUALIFYING_FORMAT", "qualifying_format", "Q1/Q2/Q3 knockout", 0.95)
    add(2024, "ENGINE_FORMULA", "power_unit", "1.6L V6 turbo hybrid", 0.95)
    add(2024, "AERO_REGULATION", "aero_generation", "ground-effect (2022 ruleset)", 0.9)
    add(2024, "PARC_FERME", "parc_ferme_from", "qualifying start", 0.85)
    return rows


def seed_evidence() -> list[dict[str, Any]]:
    """Curated evidence rows as plain dicts (for the JSON evidence layer)."""
    return [r.model_dump() for r in _seed()]


def load_evidence(root: str) -> list[dict[str, Any]]:
    """Load the regulation evidence layer file (empty list when absent)."""
    path = os.path.join(root, "data", "regulations", "regulation_evidence.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data)
