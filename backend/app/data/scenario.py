"""Historical scenario builder: canonical records -> simulation input (Phase 9E).

One-directional bridge: this module may import simulation models, but the
simulation engine never imports historical data. Performance numbers are
never invented here; the scenario carries identities, links, grid order
and environment, while actual Car/Driver pace objects stay caller-owned.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HistoricalScenario(BaseModel):
    """Simulation-ready scenario derived from canonical records."""

    scenario_id: str  # == source race_id
    season_id: str
    track_id: str  # canonical circuit_id mapped to a simulation track id
    total_laps: int | None = None
    grid_order: list[str] = Field(default_factory=list)  # driver_ids, pole first
    drivers: list[dict[str, Any]] = Field(default_factory=list)
    cars: dict[str, dict[str, str]] = Field(default_factory=dict)
    weather: dict[str, Any] = Field(default_factory=dict)
    unavailable: list[str] = Field(default_factory=list)
    provenance_chain: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


def build_scenario(
    race: dict[str, Any],
    results: list[dict[str, Any]],
    drivers: list[dict[str, Any]] | None = None,
    weather: dict[str, Any] | None = None,
    track_id_map: dict[str, str] | None = None,
) -> HistoricalScenario:
    """Build a scenario from canonical dicts (deterministic, sorted)."""
    drivers = drivers or []
    track_id_map = track_id_map or {}
    unavailable: list[str] = []
    ordered = sorted(
        (r for r in results if r.get("grid_position") is not None),
        key=lambda r: (r["grid_position"], str(r.get("driver_id"))),
    )
    grid_order = [str(r["driver_id"]) for r in ordered]
    if len(grid_order) < len(results):
        unavailable.append("grid_order:partial")
    driver_rows = []
    cars: dict[str, dict[str, str]] = {}
    known_drivers = {str(d.get("driver_id")) for d in drivers}
    for result in sorted(results, key=lambda r: str(r.get("driver_id"))):
        driver_id = str(result.get("driver_id"))
        if driver_id not in known_drivers:
            unavailable.append(f"driver:{driver_id}")
        driver_rows.append({
            "driver_id": driver_id,
            "constructor_id": str(result.get("constructor_id", "")),
            "car_id": str(result.get("car_id", "")),
        })
        cars[driver_id] = {
            "constructor_id": str(result.get("constructor_id", "")),
            "car_id": str(result.get("car_id", "")),
        }
    scheduled = race.get("scheduled_laps")
    if scheduled is None:
        unavailable.append("total_laps")
    return HistoricalScenario(
        scenario_id=str(race.get("race_id")),
        season_id=str(race.get("season_id", "")),
        track_id=track_id_map.get(str(race.get("circuit_id", "")),
                                  str(race.get("circuit_id", ""))),
        total_laps=scheduled,
        grid_order=grid_order,
        drivers=driver_rows,
        cars=cars,
        weather=dict(weather or {}),
        unavailable=sorted(set(unavailable)),
        provenance_chain=["canonical", "scenario"],
    )
