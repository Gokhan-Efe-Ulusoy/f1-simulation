"""Historical regulation metadata (Phase 9D) — curated knowledge layer.

Curated, high-confidence rules only. Every record is marked
provider="curated" so curated knowledge is never mistaken for observed
source data. Season-specific lookups return HistoricalRegulation rows.
"""
from __future__ import annotations

from app.data.models.canonical import HistoricalRegulation

_CURATED = "curated"


def _rule(season: int, domain: str, value: str, confidence: float,
          detail: dict[str, object] | None = None) -> HistoricalRegulation:
    return HistoricalRegulation(
        regulation_id=f"{season}:{domain}",
        season_id=str(season),
        domain=domain,
        value=value,
        detail=detail or {},
        confidence=confidence,
        provenance=None,
    )


def regulations_for_season(year: int) -> list[HistoricalRegulation]:
    """Return curated regulation facts applicable to a season."""
    rules: list[HistoricalRegulation] = []
    if year <= 2009:
        rules.append(_rule(year, "refuelling", "allowed", 0.9))
    else:
        rules.append(_rule(year, "refuelling", "banned", 0.95))
    if year >= 2010:
        rules.append(_rule(
            year, "points_system", "25-18-15-12-10-8-6-4-2-1", 0.95,
            {"positions": 10}))
    else:
        rules.append(_rule(year, "points_system", "pre-2010", 0.6,
                            {"note": "older systems not yet encoded"}))
    if 2019 <= year <= 2024:
        rules.append(_rule(year, "fastest_lap_point", "awarded", 0.8,
                            {"note": "one point for fastest lap in top 10"}))
    if year >= 2011:
        rules.append(_rule(year, "drs", "enabled", 0.95))
    else:
        rules.append(_rule(year, "drs", "not_present", 0.9))
    if year >= 2021:
        rules.append(_rule(year, "sprint_format", "available_on_selected_weekends", 0.9))
    else:
        rules.append(_rule(year, "sprint_format", "not_present", 0.9))
    if year >= 2018:
        rules.append(_rule(year, "halo", "mandatory", 0.9))
    return sorted(rules, key=lambda r: (r.domain, r.regulation_id))


def curated_provider_tag() -> str:
    """Provider tag used for curated (non-observed) regulation facts."""
    return _CURATED
