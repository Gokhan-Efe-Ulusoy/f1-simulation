"""Normalization: raw source records -> normalized dicts (Phase 9C).

Rules: never guess. Ambiguous or malformed values become None plus a
warning string. Units are made explicit at this layer.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_DURATION_RE = re.compile(
    r"^(?:(\d+):)?([0-5]?\d):([0-5]?\d(?:\.\d{1,3})?)$"
)

COMPOUND_ALIASES: dict[str, str] = {
    "soft": "soft", "s": "soft",
    "medium": "medium", "m": "medium",
    "hard": "hard", "h": "hard",
    "intermediate": "intermediate", "inter": "intermediate", "i": "intermediate",
    "wet": "wet", "w": "wet", "full wet": "wet",
}

SESSION_ALIASES: dict[str, str] = {
    "r": "race", "race": "race",
    "q": "qualifying", "qualifying": "qualifying",
    "q1": "qualifying_1", "q2": "qualifying_2", "q3": "qualifying_3",
    "sprint": "sprint", "sprint_shootout": "sprint_qualifying",
    "sq": "sprint_qualifying",
    "fp1": "practice_1", "fp2": "practice_2", "fp3": "practice_3",
    "practice": "practice_1",
}


def normalize_date(value: Any) -> str | None:
    """Normalize to ISO date (YYYY-MM-DD) or None when unparseable."""
    if value is None:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_duration_seconds(value: Any) -> float | None:
    """Parse 'H:MM:SS.mmm' / 'MM:SS.mmm' / '+S.mmm' / float seconds.

    Returns None for leader-time placeholders ('', '-', 'N/A') and for
    anything ambiguous. Gap strings like '+12.345' give 12.345.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "-", "N/A", "n/a", "None"):
        return None
    if text.startswith("+"):
        try:
            gap = float(text[1:])
        except ValueError:
            return None
        return gap if gap >= 0 else None
    match = _DURATION_RE.match(text)
    if match:
        hours = int(match.group(1)) if match.group(1) else 0
        return hours * 3600.0 + int(match.group(2)) * 60.0 + float(match.group(3))
    try:
        seconds = float(text)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def normalize_compound(value: Any) -> str | None:
    """Normalize a tyre compound label or None when unknown."""
    if value is None:
        return None
    key = str(value).strip().lower()
    return COMPOUND_ALIASES.get(key)


def normalize_session(value: Any) -> str | None:
    """Normalize a session name or None when unknown."""
    if value is None:
        return None
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return SESSION_ALIASES.get(key, key if key else None)


def normalize_int(value: Any) -> int | None:
    """Parse an int or None (never truncates floats silently)."""
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        return None
    return int(text)


def normalize_jolpica_result(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one Jolpica classification row. Returns (record, warnings)."""
    warnings: list[str] = []
    driver = row.get("Driver", {}) or {}
    constructor = row.get("Constructor", {}) or {}
    record: dict[str, Any] = {
        "season": normalize_int(row.get("_season")),
        "round": normalize_int(row.get("_round")),
        "race_name": str(row.get("_race_name", "")),
        "circuit_ref": str(row.get("_circuit_id", "")),
        "date": normalize_date(row.get("_date")),
        "driver_ref": str(driver.get("driverId", "")),
        "constructor_ref": str(constructor.get("constructorId", "")),
        "grid": normalize_int(row.get("grid")),
        "position": normalize_int(row.get("position")),
        "status": str(row.get("status", "")),
        "points": None,
        "fastest_lap": None,
    }
    try:
        record["points"] = float(str(row.get("points", "")).strip())
    except (ValueError, TypeError, AttributeError):
        warnings.append(f"unparseable points: {row.get('points')!r}")
    fastest = row.get("FastestLap") or {}
    if fastest.get("Time", {}).get("time"):
        parsed = normalize_duration_seconds(fastest["Time"]["time"])
        if parsed is None:
            warnings.append(f"unparseable fastest lap: {fastest['Time']['time']!r}")
        record["fastest_lap"] = parsed
        record["fastest_lap_number"] = normalize_int(fastest.get("lap"))
    time_field = row.get("Time", {})
    if isinstance(time_field, dict) and time_field.get("time"):
        record["total_time_seconds"] = normalize_duration_seconds(time_field["time"])
    else:
        # Winner rows carry "time", others carry gap in "Time" too; absence is fine.
        record["total_time_seconds"] = None
    if not record["driver_ref"]:
        warnings.append("missing driver_ref")
    return record, warnings


def normalize_csv_result(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one CSV classification row. Returns (record, warnings)."""
    warnings: list[str] = []
    record: dict[str, Any] = {
        "season": normalize_int(row.get("season")),
        "round": normalize_int(row.get("round")),
        "driver_ref": str(row.get("driver_ref", "")).strip(),
        "constructor_ref": str(row.get("constructor_ref", "")).strip(),
        "grid": normalize_int(row.get("grid")),
        "position": normalize_int(row.get("position")),
        "status": str(row.get("status", "")).strip(),
    }
    for key in ("season", "round", "grid", "position"):
        raw = row.get(key, "")
        if raw not in (None, "") and record[key] is None:
            warnings.append(f"unparseable {key}: {raw!r}")
    if not record["driver_ref"]:
        warnings.append("missing driver_ref")
    return record, warnings
