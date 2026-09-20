"""Tyre era classification — deterministic, data-driven."""
from __future__ import annotations

from enum import Enum

class TyreEra(str, Enum):
    HISTORICAL = "TYRE_ERA_HISTORICAL"  # 1950-2010, no compound data
    PIRELLI = "TYRE_ERA_PIRELLI"  # 2011-2026, modern Pirelli

# Deterministic mapping, documented in phase16_data_audit.md
def tyre_era_for_season(season: int) -> TyreEra:
    if 1950 <= season <= 2010:
        return TyreEra.HISTORICAL
    elif 2011 <= season <= 2026:
        return TyreEra.PIRELLI
    else:
        return TyreEra.HISTORICAL

def tyre_era_for_race(season: int, compound: str | None = None) -> TyreEra:
    # Compound does not change era, only season does
    return tyre_era_for_season(season)
