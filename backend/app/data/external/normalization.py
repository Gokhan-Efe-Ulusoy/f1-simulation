"""Canonical staging normalization (Phase 22.5).

Raw payloads -> canonical-shaped staging rows. Rules (same as Phase 9C):
never guess; unparseable values become None + a warning. Every row carries
provenance (source_id, source_file, source_record_id, observed_at,
ingested_at). Nothing here writes to the authoritative canonical dataset.
"""
from __future__ import annotations

from typing import Any

from app.data.normalization import (
    normalize_compound,
    normalize_date,
    normalize_duration_seconds,
    normalize_int,
)
from app.data.provenance import utc_now_iso


def _prov(source_id: str, source_file: str, record_id: str, observed_at: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_file": source_file,
        "source_record_id": record_id,
        "observed_at": observed_at,
        "ingested_at": utc_now_iso(),
    }


def normalize_jolpica_laps(
    payload: dict[str, Any], *, source_file: str, season: int, round_no: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize one Jolpica laps page (MRData envelope) to lap rows."""
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        races = payload["MRData"]["RaceTable"]["Races"]
        race = races[0]
        laps = race.get("Laps", [])
        observed_at = str(race.get("date", ""))
    except (KeyError, TypeError, IndexError) as exc:
        return [], [f"unexpected laps shape: {exc}"]
    for lap in laps:
        lap_no = normalize_int(lap.get("number"))
        for timing in lap.get("Timings", []) or []:
            secs = normalize_duration_seconds(timing.get("time"))
            if secs is None:
                warnings.append(f"unparseable lap time: {timing.get('time')!r}")
            rows.append({
                "season": season,
                "round": round_no,
                "driver_ref": str(timing.get("driverId", "")),
                "lap_number": lap_no,
                "lap_time_seconds": secs,
                "position": normalize_int(timing.get("position")),
                "provenance": _prov("jolpica-laps", source_file,
                                    f"{season}/{round_no}/lap/{lap_no}/{timing.get('driverId', '')}",  # noqa: E501
                                    observed_at),
            })
    return rows, warnings


def normalize_jolpica_pitstops(
    payload: dict[str, Any], *, source_file: str, season: int, round_no: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize one Jolpica pitstops page to pit-stop rows.

    NOTE: Jolpica `duration` is the total stop duration; stationary vs
    pit-lane loss is NOT split (kept as total_pit_loss only).
    """
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        races = payload["MRData"]["RaceTable"]["Races"]
        race = races[0]
        stops = race.get("PitStops", [])
        observed_at = str(race.get("date", ""))
    except (KeyError, TypeError, IndexError) as exc:
        return [], [f"unexpected pitstops shape: {exc}"]
    for stop in stops:
        # Duration may be seconds ('24.418') or M:SS.mmm ('1:14.773',
        # red-flag waits like '26:15.603'). Both are observed values.
        duration = normalize_duration_seconds(stop.get("duration"))
        if duration is None and stop.get("duration") not in (None, ""):
            warnings.append(f"unparseable stop duration: {stop.get('duration')!r}")
        rows.append({
            "season": season,
            "round": round_no,
            "driver_ref": str(stop.get("driverId", "")),
            "pit_lap": normalize_int(stop.get("lap")),
            "stop_number": normalize_int(stop.get("stop")),
            "time_of_day": str(stop.get("time", "")),
            "total_pit_loss_seconds": duration,
            "stationary_time_seconds": None,  # NOT split by source
            "pit_lane_time_seconds": None,  # NOT split by source
            "provenance": _prov("jolpica-pitstops", source_file,
                                f"{season}/{round_no}/stop/{stop.get('driverId', '')}/{stop.get('stop', '')}",  # noqa: E501
                                observed_at),
        })
    return rows, warnings


def normalize_openf1_laps(
    records: list[dict[str, Any]], *, source_file: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize OpenF1 /laps rows (already per-row JSON)."""
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for rec in records:
        secs = rec.get("lap_duration")
        try:
            secs_f = float(secs) if secs is not None else None
        except (ValueError, TypeError):
            secs_f = None
            warnings.append(f"unparseable lap_duration: {secs!r}")
        rows.append({
            "session_key": rec.get("session_key"),
            "meeting_key": rec.get("meeting_key"),
            "driver_number": rec.get("driver_number"),
            "lap_number": normalize_int(rec.get("lap_number")),
            "lap_time_seconds": secs_f,
            "sector_1_seconds": rec.get("duration_sector_1"),
            "sector_2_seconds": rec.get("duration_sector_2"),
            "sector_3_seconds": rec.get("duration_sector_3"),
            "speed_trap_kph": rec.get("st_speed"),
            "is_pit_in_lap": rec.get("is_pit_in_lap"),
            "is_pit_out_lap": rec.get("is_pit_out_lap"),
            "provenance": _prov("openf1-timing", source_file,
                                f"laps/{rec.get('session_key')}/{rec.get('driver_number')}/{rec.get('lap_number')}",  # noqa: E501
                                str(rec.get("date_start", ""))),
        })
    return rows, warnings


def normalize_openf1_stints(
    records: list[dict[str, Any]], *, source_file: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize OpenF1 /stints rows (observed compound + age)."""
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for rec in records:
        compound = normalize_compound(rec.get("compound"))
        if compound is None and rec.get("compound"):
            warnings.append(f"unknown compound: {rec.get('compound')!r}")
        rows.append({
            "session_key": rec.get("session_key"),
            "meeting_key": rec.get("meeting_key"),
            "driver_number": rec.get("driver_number"),
            "stint_number": normalize_int(rec.get("stint_number")),
            "compound": compound or "",
            "lap_start": normalize_int(rec.get("lap_start")),
            "lap_end": normalize_int(rec.get("lap_end")),
            "tyre_age_at_start": normalize_int(rec.get("tyre_age_at_start")),
            "provenance": _prov("openf1-stints", source_file,
                                f"stints/{rec.get('session_key')}/{rec.get('driver_number')}/{rec.get('stint_number')}",  # noqa: E501
                                ""),
        })
    return rows, warnings


def normalize_openf1_weather(
    records: list[dict[str, Any]], *, source_file: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize OpenF1 /weather rows (1-minute track sensors)."""
    rows: list[dict[str, Any]] = []
    for rec in records:
        rows.append({
            "session_key": rec.get("session_key"),
            "meeting_key": rec.get("meeting_key"),
            "date": str(rec.get("date", "")),
            "air_temperature_c": rec.get("air_temperature"),
            "track_temperature_c": rec.get("track_temperature"),
            "humidity_percent": rec.get("humidity"),
            "pressure_mbar": rec.get("pressure"),
            "rainfall": rec.get("rainfall"),
            "wind_speed_ms": rec.get("wind_speed"),
            "wind_direction_deg": rec.get("wind_direction"),
            "provenance": _prov("openf1-weather", source_file,
                                f"weather/{rec.get('session_key')}/{rec.get('date', '')}", str(rec.get("date", ""))),  # noqa: E501
        })
    return rows, []


def normalize_openf1_pit(
    records: list[dict[str, Any]], *, source_file: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize OpenF1 /pit rows (observed pit durations)."""
    rows: list[dict[str, Any]] = []
    for rec in records:
        rows.append({
            "session_key": rec.get("session_key"),
            "meeting_key": rec.get("meeting_key"),
            "driver_number": rec.get("driver_number"),
            "lap_number": normalize_int(rec.get("lap_number")),
            "pit_duration_seconds": rec.get("pit_duration"),
            "date": str(rec.get("date", "")),
            "provenance": _prov("openf1-pit", source_file,
                                f"pit/{rec.get('session_key')}/{rec.get('driver_number')}/{rec.get('lap_number')}",  # noqa: E501
                                str(rec.get("date", ""))),
        })
    return rows, []


def normalize_openf1_race_control(
    records: list[dict[str, Any]], *, source_file: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize OpenF1 /race_control rows (flags/incidents, observed)."""
    rows: list[dict[str, Any]] = []
    for rec in records:
        rows.append({
            "session_key": rec.get("session_key"),
            "meeting_key": rec.get("meeting_key"),
            "date": str(rec.get("date", "")),
            "category": str(rec.get("category", "")),
            "flag": str(rec.get("flag", "")) if rec.get("flag") is not None else "",
            "lap_number": normalize_int(rec.get("lap_number")),
            "sector": rec.get("sector"),
            "message": str(rec.get("message", "")),
            "scope": str(rec.get("scope", "")) if rec.get("scope") is not None else "",
            "driver_number": rec.get("driver_number"),
            "provenance": _prov("openf1-racecontrol", source_file,
                                f"rc/{rec.get('session_key')}/{rec.get('date', '')}", str(rec.get("date", ""))),  # noqa: E501
        })
    return rows, []


def normalize_openmeteo_hourly(
    payload: dict[str, Any], *, source_file: str, latitude: float, longitude: float, race_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize Open-Meteo archive hourly series. Labeled REANALYSIS (not a sensor)."""
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    hourly = payload.get("hourly") or {}
    times = hourly.get("time", []) or []
    n = len(times)
    if n == 0:
        return [], ["empty hourly series"]
    def col(name: str) -> list:
        vals = hourly.get(name, []) or []
        if len(vals) != n:
            warnings.append(f"column {name} length {len(vals)} != {n}")
            vals = list(vals) + [None] * (n - len(vals))
        return vals
    temp = col("temperature_2m")
    rh = col("relative_humidity_2m")
    pr = col("precipitation")
    psl = col("pressure_msl")
    ws = col("wind_speed_10m")
    wd = col("wind_direction_10m")
    for i, stamp in enumerate(times):
        rows.append({
            "race_id": race_id,
            "kind": "REANALYSIS",  # never confused with track sensors
            "requested_lat": latitude,
            "requested_lon": longitude,
            "grid_lat": payload.get("latitude"),
            "grid_lon": payload.get("longitude"),
            "elevation_m": payload.get("elevation"),
            "timestamp": str(stamp),
            "air_temperature_c": temp[i],
            "humidity_percent": rh[i],
            "precipitation_mm": pr[i],
            "pressure_msl_hpa": psl[i],
            "wind_speed_10m_kmh": ws[i],
            "wind_direction_10m_deg": wd[i],
            "provenance": _prov("openmeteo-era5", source_file, f"{race_id}/{stamp}", str(stamp)),
        })
    return rows, warnings


def normalize_date_only(value: Any) -> str:
    """Best-effort ISO date for staging joins ('' when unparseable)."""
    return normalize_date(value) or ""
