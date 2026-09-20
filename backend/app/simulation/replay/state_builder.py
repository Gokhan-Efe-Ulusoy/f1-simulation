"""Phase 22 — Historical race loading with strict observation cutoffs.

Loads canonical races/results without inventing anything. `as_of` is always
race_date minus one day (the project's strict contract). The observed result
(final positions etc.) is returned as a validation target ONLY — callers must
never feed it into the simulation decision layer.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.simulation.replay.models import HistoricalRace


def data_root() -> Path:
    """Canonical data root, robust to backend/ vs repo-root cwd."""
    here = Path(__file__).resolve()
    for parent in [Path.cwd(), here, *here.parents]:
        cand = parent / "backend" / "data" / "canonical" / "races.json"
        if cand.exists():
            return parent / "backend" / "data"
        cand2 = parent / "data" / "canonical" / "races.json"
        if cand2.exists():
            return parent / "data"
    raise FileNotFoundError("canonical races.json not found from cwd or package path")


def as_of_for_race_date(race_date: str) -> str:
    """as_of = race_date - 1 day (strict_before contract)."""
    iso = race_date.replace("Z", "+00:00")
    if "T" not in iso:
        iso = iso + "T00:00:00+00:00"
    dt = datetime.fromisoformat(iso)
    return (dt - timedelta(days=1)).isoformat().replace("+00:00", "Z")


def load_race_record(race_id: str) -> dict[str, Any]:
    root = data_root()
    races = json.loads((root / "canonical" / "races.json").read_text())
    for race in races:
        if race.get("race_id") == race_id:
            return race
    raise ValueError(f"race {race_id!r} not found in canonical races")


def load_race_results(race_id: str) -> list[dict[str, Any]]:
    root = data_root()
    results = json.loads((root / "canonical" / "results.json").read_text())
    return [r for r in results if r.get("race_id") == race_id]


def load_pit_stops(race_id: str) -> list[dict[str, Any]]:
    """Canonical pit stops for a race (often absent -> NON_IDENTIFIABLE)."""
    try:
        root = data_root()
        pits = json.loads((root / "canonical" / "pit_stops.json").read_text())
        return [p for p in pits if p.get("race_id") == race_id]
    except Exception:
        return []


def load_historical_race(race_id: str) -> HistoricalRace:
    """Build a HistoricalRace: pre-race observables + validation-only result."""
    from app.data.scenario import build_scenario

    race = load_race_record(race_id)
    rows = load_race_results(race_id)
    hist = build_scenario(race, rows)
    race_date = str(race.get("date", ""))
    as_of = as_of_for_race_date(race_date)
    observed: dict[str, Any] = {}
    for row in rows:
        did = str(row.get("driver_id"))
        observed[did] = {
            "final_position": row.get("final_position"),
            "grid_position": row.get("grid_position"),
            "status": row.get("status"),
            "points": row.get("points"),
            "fastest_lap_seconds": row.get("fastest_lap_seconds"),
            "validation_only": True,
        }
    unavailable = sorted(set(hist.unavailable))
    total_laps = hist.total_laps
    evidence: dict[str, str] = {
        "grid_order": "LIMITED" if hist.grid_order else "NON_IDENTIFIABLE",
        "identities": "LIMITED" if hist.drivers else "NON_IDENTIFIABLE",
        "total_laps": "LIMITED" if total_laps is not None else "NON_IDENTIFIABLE",
        "weather": "NON_IDENTIFIABLE",
        "setup": "NON_IDENTIFIABLE",
        "fuel": "NON_IDENTIFIABLE",
        "strategy": "NON_IDENTIFIABLE",
        "tyre_compounds": "NON_IDENTIFIABLE",
        "pit_history": "LIMITED" if load_pit_stops(race_id) else "NON_IDENTIFIABLE",
        "observed_result": "LIMITED",
    }
    if total_laps is None:
        unavailable.append("total_laps")
    return HistoricalRace(
        race_id=race_id,
        season_id=str(race.get("season_id", "")),
        round=race.get("round"),
        circuit_id=str(hist.track_id),
        race_date=race_date,
        as_of=as_of,
        total_laps=total_laps,
        total_laps_tier=evidence["total_laps"],
        scenario_id=hist.scenario_id,
        grid_order=list(hist.grid_order),
        drivers=[dict(d) for d in hist.drivers],
        observed_result=observed,
        observed_result_validation_only=True,
        unavailable=sorted(set(unavailable)),
        evidence_summary=evidence,
    )


def build_scenario_for_race(
    hrace: HistoricalRace, laps: int | None = None, scenario_type: str = "historical",
) -> Any:
    """HistoricalRace -> simulation Scenario (pre-race information only).

    The observed result is NEVER copied into the scenario. `laps` overrides
    the race distance (checkpoints / shortened test races); None keeps the
    canonical value or the engine default (58) with NON_IDENTIFIABLE noted.
    """
    from app.data.scenario import HistoricalScenario
    from app.simulation.scenario_v14 import ScenarioResolver

    hist = HistoricalScenario(
        scenario_id=hrace.scenario_id,
        season_id=hrace.season_id,
        track_id=hrace.circuit_id,
        total_laps=hrace.total_laps,
        grid_order=list(hrace.grid_order),
        drivers=[dict(d) for d in hrace.drivers],
        cars={d["driver_id"]: {"constructor_id": d.get("constructor_id", ""), "car_id": d.get("car_id", "")} for d in hrace.drivers},  # noqa: E501
        weather={},
        unavailable=list(hrace.unavailable),
        provenance_chain=["canonical", "scenario", "replay-v1.0.0"],
    )
    scenario = ScenarioResolver.from_historical(
        hist, race_date=hrace.race_date, as_of=hrace.as_of,
        scenario_type=scenario_type,  # type: ignore[arg-type]
    )
    if laps is not None:
        scenario.race_distance["laps"] = int(laps)
    return scenario
