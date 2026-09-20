"""Data-availability tiers and coverage queries (Phase 9A).

Resolution differs by era; this module states what the platform can
answer without guessing. No historical values live here.
"""
from __future__ import annotations

from app.data.models.canonical import DataAvailability

# Field -> (first season with plausible coverage, resolution).
# Conservative, documented estimates of *source* coverage, not promises.
COVERAGE_TIERS: dict[str, tuple[int, str]] = {
    "race_results": (1950, "race"),
    "qualifying": (1950, "race"),
    "championship": (1950, "race"),
    "circuits": (1950, "race"),
    "drivers": (1950, "race"),
    "constructors": (1950, "race"),
    "fastest_laps": (1950, "race"),
    "pit_stops": (1980, "race"),
    "lap_timing": (2000, "lap"),
    "tyre_stints": (2000, "race"),
    "sectors": (2010, "sector"),
    "weather": (2010, "race"),
    "telemetry": (2020, "telemetry"),
    "positions": (2020, "lap"),
}


def availability_for(field: str, season: int, source: str = "") -> DataAvailability:
    """Build an availability record for one field/season (no guessing)."""
    tier = COVERAGE_TIERS.get(field)
    if tier is None:
        return DataAvailability(field=field, available=False, source=source)
    start, resolution = tier
    if season < start:
        return DataAvailability(
            field=field, available=False, source=source,
            coverage_start=start, resolution=resolution, confidence=1.0,
        )
    # At/after the tier start, coverage is *possible*, not guaranteed.
    return DataAvailability(
        field=field, available=True, source=source,
        coverage_start=start, resolution=resolution, confidence=0.7,
    )


def has_coverage(field: str, season: int) -> bool:
    """Quick predicate: is this field plausibly covered for this season?"""
    return availability_for(field, season).available
