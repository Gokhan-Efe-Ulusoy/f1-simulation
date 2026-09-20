"""Historical coverage report: machine- + human-readable (Phase 9F)."""
from __future__ import annotations

from app.data.availability import COVERAGE_TIERS, availability_for

TRACKED_FIELDS = ("race_results", "qualifying", "lap_timing", "telemetry",
                  "sectors", "tyre_stints", "pit_stops", "weather")


def season_coverage(season: int) -> dict[str, dict[str, object]]:
    """Availability snapshot for one season (no data access needed)."""
    snapshot: dict[str, dict[str, object]] = {}
    for field in TRACKED_FIELDS:
        record = availability_for(field, season)
        snapshot[field] = {
            "available": record.available,
            "resolution": record.resolution,
            "confidence": record.confidence,
        }
    return snapshot


def build_coverage_report(start: int = 1950, end: int = 2026) -> dict[str, object]:
    """Build the full coverage report over a season range."""
    seasons = {str(year): season_coverage(year) for year in range(start, end + 1)}
    summary = {}
    for field in TRACKED_FIELDS:
        covered = [y for y in range(start, end + 1) if seasons[str(y)][field]["available"]]
        summary[field] = {
            "first_season": covered[0] if covered else None,
            "seasons_covered": len(covered),
        }
    return {"seasons": seasons, "summary": summary,
            "tiers": {k: {"since": v[0], "resolution": v[1]}
                      for k, v in sorted(COVERAGE_TIERS.items())}}


def render_text(report: dict[str, object], sample_years: list[int] | None = None) -> str:
    """Human-readable coverage table for sampled seasons."""
    from typing import Any, cast

    sample_years = sample_years or [1950, 1990, 2015, 2026]
    seasons = cast(dict[str, Any], report["seasons"])
    header = "season | " + " | ".join(f"{f[:10]:>10}" for f in TRACKED_FIELDS)
    lines = [header]
    for year in sample_years:
        row = seasons.get(str(year), {})
        cells = []
        for field in TRACKED_FIELDS:
            cell = row.get(field, {})
            if not cell.get("available"):
                cells.append(f"{'x':>10}")
            elif str(cell.get("resolution")) in ("lap", "sector", "telemetry"):
                cells.append(f"{'full':>10}")
            else:
                cells.append(f"{'partial':>10}")
        lines.append(f"{year} | " + " | ".join(cells))
    return "\n".join(lines)
