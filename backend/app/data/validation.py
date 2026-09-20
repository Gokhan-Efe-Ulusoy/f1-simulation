"""Canonical data validation engine (Phase 9C).

Pure functions over canonical records; every finding names the record.
No auto-repair: problems are reported, never silently fixed.
"""
from __future__ import annotations

from typing import Any

from app.data.models.canonical import DataQualityReport


def _is_iso_date(value: str) -> bool:
    parts = value.split("-")
    return (
        len(parts) == 3 and len(parts[0]) == 4
        and all(p.isdigit() for p in parts)
    )


def validate_bundle(
    dataset_version: str,
    races: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | None = None,
    drivers: list[dict[str, Any]] | None = None,
    constructors: list[dict[str, Any]] | None = None,
) -> DataQualityReport:
    """Validate one canonical bundle; returns errors + warnings + stats."""
    races = races or []
    results = results or []
    drivers = drivers or []
    constructors = constructors or []
    errors: list[str] = []
    warnings: list[str] = []

    # --- duplicate detection ---
    for kind, items, key in (
        ("race", races, "race_id"),
        ("result", results, "result_id"),
        ("driver", drivers, "driver_id"),
        ("constructor", constructors, "constructor_id"),
    ):
        seen: set[str] = set()
        for item in items:
            value = str(item.get(key, ""))
            if not value:
                errors.append(f"{kind} with empty {key}")
            elif value in seen:
                errors.append(f"duplicate {kind}: {value}")
            else:
                seen.add(value)

    # --- races ---
    for race in races:
        rid = race.get("race_id", "?")
        if race.get("date") and not _is_iso_date(str(race["date"])):
            errors.append(f"race {rid}: impossible date {race['date']!r}")
        scheduled = race.get("scheduled_laps")
        if scheduled is not None and (scheduled < 3 or scheduled > 120):
            errors.append(f"race {rid}: impossible lap count {scheduled!r}")
        if not race.get("circuit_id"):
            warnings.append(f"race {rid}: missing circuit link")

    # --- results ---
    race_ids = {str(r.get("race_id")) for r in races}
    driver_ids = {str(d.get("driver_id")) for d in drivers}
    constructor_ids = {str(c.get("constructor_id")) for c in constructors}
    for result in results:
        rid = result.get("result_id", "?")
        if race_ids and str(result.get("race_id")) not in race_ids:
            errors.append(f"result {rid}: orphaned race {result.get('race_id')!r}")
        if driver_ids and str(result.get("driver_id")) not in driver_ids:
            errors.append(f"result {rid}: orphaned driver {result.get('driver_id')!r}")
        if constructor_ids and result.get("constructor_id") \
                and str(result.get("constructor_id")) not in constructor_ids:
            errors.append(
                f"result {rid}: orphaned constructor {result.get('constructor_id')!r}")
        for field in ("grid_position", "final_position"):
            field_value = result.get(field)
            if isinstance(field_value, (int, float)) and not isinstance(field_value, bool) \
                    and (field_value < 1 or field_value > 40):
                errors.append(f"result {rid}: invalid {field} {field_value!r}")
        for field in ("total_time_seconds", "time_gap_seconds", "fastest_lap_seconds"):
            time_value = result.get(field)
            if isinstance(time_value, (int, float)) and not isinstance(time_value, bool) \
                    and time_value < 0:
                errors.append(f"result {rid}: negative {field} {time_value!r}")
        laps = result.get("laps_completed")
        if isinstance(laps, (int, float)) and not isinstance(laps, bool) and laps < 0:
            errors.append(f"result {rid}: negative laps {laps!r}")
    # points consistency: winner must not have fewer points than P2
    by_race: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_race.setdefault(str(result.get("race_id")), []).append(result)
    for race_id, rows in by_race.items():
        ordered = sorted(
            [r for r in rows if r.get("final_position") is not None],
            key=lambda r: r["final_position"],
        )
        for first, second in zip(ordered, ordered[1:], strict=False):
            points_first = first.get("points")
            points_second = second.get("points")
            if points_first is not None and points_second is not None \
                    and points_first < points_second:
                errors.append(f"race {race_id}: inconsistent points "
                              f"P{first.get('final_position')} < P{second.get('final_position')}")
                break

    statistics = {
        "races": len(races),
        "results": len(results),
        "drivers": len(drivers),
        "constructors": len(constructors),
    }
    return DataQualityReport(
        dataset_version=dataset_version,
        errors=sorted(errors),
        warnings=sorted(warnings),
        statistics=statistics,
        coverage={},
        source_conflicts=0,
    )
