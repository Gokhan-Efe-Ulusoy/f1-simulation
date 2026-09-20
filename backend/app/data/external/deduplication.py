"""Deterministic row identity + duplicate protection (Phase 22.5).

Identity follows the spec: season/round/session/driver/lap/timestamp/
variable. Duplicates against the canonical set are reported, never merged.
"""
from __future__ import annotations

from typing import Any


def row_identity(row: dict[str, Any], table: str) -> str:
    """Build a deterministic identity string for one staging row."""
    driver = row.get("driver_ref") or row.get("driver_number")
    if table == "laps":
        # Jolpica rows key on season/round; OpenF1 rows on session_key.
        event = f"{row.get('season')}/{row.get('round')}" if row.get("season") is not None \
            else f"session/{row.get('session_key')}"
        return f"laps|{event}|{driver}|{row.get('lap_number')}"
    if table == "pit_stops":
        lap = row.get("pit_lap") if row.get("pit_lap") is not None else row.get("lap_number")
        stop = row.get("stop_number", "")
        stamp = row.get("date", "") or ""
        event = f"{row.get('season')}/{row.get('round')}" if row.get("season") is not None \
            else f"session/{row.get('session_key')}"
        return f"pit|{event}|{driver}|{lap}|{stop}|{stamp}"
    if table == "stints":
        return (
            f"stint|{row.get('session_key')}|{row.get('driver_number')}|{row.get('stint_number')}"
        )
    if table == "weather":
        return f"wx|{row.get('session_key')}|{row.get('date')}"
    if table == "race_control":
        return f"rc|{row.get('session_key')}|{row.get('date')}|{row.get('message', '')[:48]}"
    if table == "reanalysis":
        return f"rean|{row.get('race_id')}|{row.get('timestamp')}"
    return f"{table}|{sorted((k, str(v)) for k, v in row.items() if k != 'provenance')}"


def deduplicate(
    rows: list[dict[str, Any]],
    table: str,
    known_identities: set[str] | None = None,
) -> dict[str, Any]:
    """Split rows into new/duplicate/invalid with deterministic identity.

    `known_identities` holds identities already present in canonical (or an
    earlier staging batch). Within-batch repeats also count as duplicates.
    """
    known = set(known_identities or set())
    seen: set[str] = set()
    new_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    for row in rows:
        identity = row_identity(row, table)
        driver = row.get("driver_ref") or row.get("driver_number")
        lap = row.get("lap_number") if table != "pit_stops" else (
            row.get("pit_lap") if row.get("pit_lap") is not None else row.get("lap_number"))
        if table in ("laps", "pit_stops") and (driver is None or lap is None):
            invalid_rows.append({**row, "_identity": identity})
            continue
        if identity in known or identity in seen:
            duplicate_rows.append({**row, "_identity": identity})
            continue
        seen.add(identity)
        new_rows.append({**row, "_identity": identity})
    return {
        "table": table,
        "new_rows": len(new_rows),
        "duplicate_rows": len(duplicate_rows),
        "invalid_rows": len(invalid_rows),
        "new": new_rows,
    }
