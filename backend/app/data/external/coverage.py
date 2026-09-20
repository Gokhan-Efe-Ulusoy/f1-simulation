"""Coverage audit + calibration-readiness (Phase 22.5).

Before/after matrix over the tracked variables and per-variable readiness
records for `backend/data/calibration_candidates/`. No improvement is
claimed without actual observations.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

ERAS: list[str] = [
    "1950-1969", "1970-1989", "1990-1999", "2000-2009",
    "2010-2017", "2018-2021", "2022-2026",
]

#: Baseline tiers carried over from the Phase 22 historical audit.
BASELINE_TIERS: dict[str, str] = {
    "race_results": "FULL",
    "qualifying": "PARTIAL",
    "lap_timing": "LIMITED",
    "sector_timing": "LIMITED",
    "pit_timing": "PARTIAL",
    "tyre_compound": "LIMITED",
    "tyre_age": "PRIOR_ONLY",
    "weather": "LIMITED",
    "race_control": "LIMITED",
    "telemetry": "LIMITED",
    "setup": "NON_IDENTIFIABLE",
    "strategy": "NON_IDENTIFIABLE",
    "regulation": "LIMITED",
}


class CalibrationCandidate(BaseModel):
    """Readiness record for one calibratable variable."""

    variable: str = ""
    sample_size: int = 0
    years: str = ""
    circuits: int = 0
    drivers: int = 0
    observations: int = 0
    confounders: list[str] = Field(default_factory=list)
    candidate_model: str = ""
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}


def build_coverage_matrix(
    acquired_counts: dict[str, int],
    acquired_eras: dict[str, list[str]],
    canonical_changed: bool = False,
) -> list[dict[str, Any]]:
    """Build the before/after matrix. `acquired_*` keyed by variable."""
    matrix: list[dict[str, Any]] = []
    for variable, current in BASELINE_TIERS.items():
        count = acquired_counts.get(variable, 0)
        eras = acquired_eras.get(variable, [])
        if count > 0 and not canonical_changed:
            canonical = f"STAGED ({count} obs, eras {eras}); canonical {current} unchanged"
            delta = f"+{count} staged observations in {eras or 'no era'}"
        elif count > 0:
            canonical = f"PROMOTED ({count} obs)"
            delta = f"+{count} observations"
        else:
            canonical = f"unchanged ({current})"
            delta = "no change (no observations acquired)"
        matrix.append({
            "variable": variable,
            "current": current,
            "acquired": count,
            "canonical": canonical,
            "coverage_change": delta,
        })
    return matrix


def build_readiness(
    stats: dict[str, dict[str, Any]],
) -> list[CalibrationCandidate]:
    """Build readiness records from per-variable acquisition stats.

    `stats[variable]` keys: sample_size, years, circuits, drivers,
    observations, confounders, candidate_model, evidence_tier.
    """
    out: list[CalibrationCandidate] = []
    for variable, spec in stats.items():
        out.append(CalibrationCandidate(
            variable=variable,
            sample_size=int(spec.get("sample_size", 0)),
            years=str(spec.get("years", "")),
            circuits=int(spec.get("circuits", 0)),
            drivers=int(spec.get("drivers", 0)),
            observations=int(spec.get("observations", 0)),
            confounders=list(spec.get("confounders", [])),
            candidate_model=str(spec.get("candidate_model", "")),
            evidence_tier=str(spec.get("evidence_tier", "PRIOR_ONLY")),
        ))
    return sorted(out, key=lambda c: c.variable)


def era_for_season(season: int) -> str:
    """Map a season to its reporting era."""
    bounds = [(1950, 1969), (1970, 1989), (1990, 1999), (2000, 2009),
              (2010, 2017), (2018, 2021), (2022, 2026)]
    for (lo, hi), era in zip(bounds, ERAS):
        if lo <= season <= hi:
            return era
    return "out-of-range"
