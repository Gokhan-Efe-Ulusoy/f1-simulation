"""Conflict detection across overlapping observations (Phase 22.5).

Differences are classified as rounding / precision / genuine conflict /
schema mismatch. Nothing is silently selected: every conflict becomes a
record in `external_conflicts.json` + the conflict audit doc.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConflictRecord(BaseModel):
    """One detected disagreement between two observations."""

    entity: str = Field(description="Deterministic identity of the observation")
    variable: str = ""
    source_a: str = ""
    value_a: float | str | None = None
    source_b: str = ""
    value_b: float | str | None = None
    abs_diff: float | None = None
    classification: str = Field(
        default="genuine_conflict",
        description="rounding | timestamp_precision | genuine_conflict | schema_mismatch",
    )
    note: str = ""

    model_config = {"use_enum_values": True}


def classify_numeric_diff(
    value_a: float, value_b: float, *, rounding_tol: float = 0.002
) -> tuple[str, float]:
    """Classify a numeric disagreement. Returns (class, abs_diff)."""
    diff = abs(value_a - value_b)
    if diff <= rounding_tol:
        return "rounding", diff
    return "genuine_conflict", diff


def detect_lap_conflicts(
    jolpica_rows: list[dict[str, Any]],
    openf1_rows: list[dict[str, Any]],
    *,
    season: int,
    round_no: int,
    driver_map: dict[str, str] | None = None,
    rounding_tol: float = 0.002,
) -> list[ConflictRecord]:
    """Compare Jolpica lap times vs OpenF1 lap durations for one race.

    `driver_map` maps OpenF1 driver_number -> jolpica driver_ref. Without a
    mapping (or without driver metadata for the session), pairs that cannot
    be joined are skipped — never guessed.
    """
    driver_map = driver_map or {}
    jolpica_index: dict[tuple[str, int], float] = {}
    for row in jolpica_rows:
        if row.get("season") != season or row.get("round") != round_no:
            continue
        secs = row.get("lap_time_seconds")
        if secs is None:
            continue
        jolpica_index[(str(row.get("driver_ref")), int(row.get("lap_number") or -1))] = float(secs)
    conflicts: list[ConflictRecord] = []
    for row in openf1_rows:
        num = str(row.get("driver_number", ""))
        ref = driver_map.get(num)
        if ref is None:
            continue  # cannot join identities: skip, do not guess
        lap = row.get("lap_number")
        secs = row.get("lap_time_seconds")
        if lap is None or secs is None:
            continue
        key = (ref, int(lap))
        if key not in jolpica_index:
            continue
        cls, diff = classify_numeric_diff(jolpica_index[key], float(secs), rounding_tol=rounding_tol)  # noqa: E501
        if cls != "rounding":
            conflicts.append(ConflictRecord(
                entity=f"laps|{season}|{round_no}|{ref}|{lap}",
                variable="lap_time_seconds",
                source_a="jolpica-laps",
                value_a=jolpica_index[key],
                source_b="openf1-timing",
                value_b=float(secs),
                abs_diff=diff,
                classification=cls,
                note="sources disagree beyond rounding tolerance",
            ))
    return conflicts


def conflict_pattern(conflicts: list[ConflictRecord]) -> dict[str, object]:
    """Summarize the shape of a conflict set (systematic vs scattered).

    A single-lap, single-sign offset (e.g. all lap-1, one source slower)
    indicates a definition difference (start-line timing) rather than
    random measurement disagreement. Returned as plain data for manifests.
    """
    if not conflicts:
        return {"pattern": "no_conflicts", "n": 0}
    laps = {c.entity.split("|")[-1] for c in conflicts}
    signs = {(c.value_b or 0) - (c.value_a or 0) > 0 for c in conflicts
             if isinstance(c.value_a, (int, float)) and isinstance(c.value_b, (int, float))}
    if len(laps) == 1 and len(signs) == 1:
        only_lap = next(iter(laps))
        direction = "B_slower" if next(iter(signs)) else "A_slower"
        return {"pattern": "systematic_single_lap_offset", "lap": only_lap,
                "direction": direction, "n": len(conflicts),
                "interpretation": ("all disagreements on one lap with one sign: "
                                   "start/lap-1 timing definition differs between sources")}
    return {"pattern": "scattered", "n": len(conflicts),
            "distinct_laps": len(laps)}


def detect_result_conflicts(
    canonical_results: list[dict[str, Any]],
    staging_results: list[dict[str, Any]],
) -> list[ConflictRecord]:
    """Compare already-canonical classifications vs a new staging batch."""
    index: dict[str, dict[str, Any]] = {}
    for row in canonical_results:
        key = f"{row.get('race_id')}|{row.get('driver_id')}"
        index[key] = row
    conflicts: list[ConflictRecord] = []
    for row in staging_results:
        key = f"{row.get('race_id')}|{row.get('driver_id')}"
        if key not in index:
            continue
        base = index[key]
        for field in ("final_position", "points", "grid_position"):
            old, new = base.get(field), row.get(field)
            if old is not None and new is not None and old != new:
                conflicts.append(ConflictRecord(
                    entity=key, variable=field,
                    source_a="canonical", value_a=old,
                    source_b=str(row.get("provenance", {}).get("source_id", "staging")),
                    value_b=new, abs_diff=None,
                    classification="genuine_conflict",
                    note="staging disagrees with canonical; canonical unchanged",
                ))
    return conflicts
