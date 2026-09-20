"""Phase 28 — Race discovery service (cached canonical metadata)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _canonical_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [Path.cwd(), here, *here.parents]:
        cand = parent / "backend" / "data" / "canonical" / "races.json"
        if cand.exists():
            return parent / "backend" / "data"
        cand2 = parent / "data" / "canonical" / "races.json"
        if cand2.exists():
            return parent / "data"
    # fallback to backend/data
    return Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def _load_races_raw() -> list[dict[str, Any]]:
    try:
        root = _canonical_root()
        data = json.loads((root / "canonical" / "races.json").read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


@lru_cache(maxsize=1)
def _load_results_raw() -> list[dict[str, Any]]:
    try:
        root = _canonical_root()
        data = json.loads((root / "canonical" / "results.json").read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _race_availability(race: dict[str, Any]) -> str:
    unavailable = race.get("unavailable") or []
    if unavailable:
        return "partial"
    return "available"


def list_races(
    season: str | None = None,
    circuit: str | None = None,
    driver: str | None = None,
    constructor: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    races = _load_races_raw()
    # build driver/constructor index from results if filtering
    results = _load_results_raw() if (driver or constructor) else []
    # filter
    filtered: list[dict[str, Any]] = []
    for r in races:
        if season and str(r.get("season_id", "")) != str(season):
            continue
        if (
            circuit
            and str(r.get("circuit_id", "")).lower() != str(circuit).lower()
            and str(r.get("track_id", "")).lower() != str(circuit).lower()
        ):
            continue
        if driver or constructor:
            rid = r.get("race_id")
            rows = [x for x in results if x.get("race_id") == rid]
            if driver and not any(str(x.get("driver_id")) == driver for x in rows):
                continue
            if constructor and not any(
                str(x.get("constructor_id")) == constructor or str(x.get("team_id")) == constructor
                for x in rows
            ):
                continue
        filtered.append(r)
    total = len(filtered)
    # paginate
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    page = filtered[offset : offset + limit]
    out: list[dict[str, Any]] = []
    for r in page:
        out.append(
            {
                "race_id": r.get("race_id"),
                "season_id": r.get("season_id"),
                "round": r.get("round"),
                "circuit_id": r.get("circuit_id") or r.get("track_id"),
                "race_date": r.get("date") or r.get("race_date"),
                "total_laps": r.get("total_laps"),
                "availability": _race_availability(r),
                "unavailable": r.get("unavailable", []),
            }
        )
    return out, total


def get_race(race_id: str) -> dict[str, Any] | None:
    races = _load_races_raw()
    for r in races:
        if str(r.get("race_id")) == str(race_id):
            # enrich with grid/results count
            results = [x for x in _load_results_raw() if str(x.get("race_id")) == str(race_id)]
            return {
                "race_id": r.get("race_id"),
                "season_id": r.get("season_id"),
                "round": r.get("round"),
                "circuit_id": r.get("circuit_id") or r.get("track_id"),
                "race_date": r.get("date") or r.get("race_date"),
                "total_laps": r.get("total_laps"),
                "circuit_name": r.get("circuit_name") or r.get("name"),
                "availability": _race_availability(r),
                "unavailable": r.get("unavailable", []),
                "driver_count": len(results),
                "raw": r,
            }
    return None


# Fallback calendar for when canonical not available: 6 tracks
def _fallback_tracks() -> list[dict[str, Any]]:
    try:
        from app.simulation.models.track import get_2024_calendar

        cals = get_2024_calendar()
        return [
            {
                "race_id": f"2024-{t.id}",
                "season_id": "2024",
                "circuit_id": t.id,
                "race_date": "2024-01-01",
                "total_laps": t.number_of_laps,
                "availability": "available",
            }
            for t in cals
        ]
    except Exception:
        return []
