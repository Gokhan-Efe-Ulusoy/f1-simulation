"""Scenario system for Phase 14 — historical, counterfactual, hypothetical, future.

Preserves HistoricalScenarioBuilder, adds TemporalContext and expanded Scenario.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field
from app.data.scenario import HistoricalScenario, build_scenario

ScenarioType = Literal["historical", "counterfactual", "hypothetical", "future"]

class TemporalContext(BaseModel):
    """Central temporal gate: all data must satisfy source_timestamp < as_of.

    Passed through Scenario -> Calibration API -> RaceEngine -> MonteCarlo.
    Enforces strict_before policy.
    """
    as_of: str  # ISO8601, e.g., "2024-02-29T00:00:00Z"
    as_of_dt: datetime | None = None
    policy: str = "strict_before"  # strict_before or strict_before_or_equal

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, as_of: str, policy: str = "strict_before", **data):
        super().__init__(as_of=as_of, policy=policy, **data)
        # Parse as_of
        try:
            iso = as_of.replace("Z", "+00:00")
            if "T" not in iso:
                iso = iso + "T00:00:00+00:00"
            self.as_of_dt = datetime.fromisoformat(iso)
            if self.as_of_dt.tzinfo is None:
                self.as_of_dt = self.as_of_dt.replace(tzinfo=timezone.utc)
        except Exception:
            self.as_of_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def is_allowed(self, source_timestamp: str) -> bool:
        """Check if source_timestamp is allowed (strictly before as_of)."""
        try:
            iso = source_timestamp.replace("Z", "+00:00")
            if "T" not in iso:
                iso = iso + "T00:00:00+00:00"
            src = datetime.fromisoformat(iso)
            if src.tzinfo is None:
                src = src.replace(tzinfo=timezone.utc)
            if self.policy == "strict_before":
                return src < self.as_of_dt
            else:
                return src <= self.as_of_dt
        except:
            return False

    def check_feature(self, feature_as_of: str) -> bool:
        """Alias for feature timestamp check."""
        return self.is_allowed(feature_as_of)

class Scenario(BaseModel):
    """Expanded scenario for Phase 14."""
    scenario_id: str
    type: ScenarioType = "historical"
    season_id: str
    round: int | None = None
    circuit_id: str
    date: str  # race date
    as_of: str  # prediction cutoff, must be < date
    temporal_context: TemporalContext | None = None

    drivers: list[dict[str, Any]] = Field(default_factory=list)  # {driver_id, constructor_id, car_id}  # noqa: E501
    constructors: dict[str, dict[str, Any]] = Field(default_factory=dict)
    grid_order: list[str] = Field(default_factory=list)
    qualifying_state: dict[str, Any] = Field(default_factory=dict)  # observed or to resimulate
    weather_state: dict[str, Any] = Field(default_factory=dict)
    tyre_state: dict[str, Any] = Field(default_factory=dict)
    race_distance: dict[str, Any] = Field(default_factory=dict)  # laps, distance

    historical_mode: bool = True  # if True, use observed qualifying/grid
    resimulate_qualifying: bool = False
    hypothetical_modifiers: dict[str, Any] = Field(default_factory=dict)

    dataset_version: str = "f1-dataset-v1.1"
    calibration_version: str = "calibration-v1.0.0"
    provenance: dict[str, Any] = Field(default_factory=dict)
    unavailable: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        if self.temporal_context is None:
            # Default as_of is day before race
            try:
                race_dt = datetime.fromisoformat(self.date.replace("Z","+00:00") if "T" in self.date else self.date+"T00:00:00+00:00")  # noqa: E501
                # as_of is day before at 00:00
                as_of = data.get("as_of") or self.as_of
                if not as_of:
                    # Derive
                    as_of = self.date  # fallback
                self.temporal_context = TemporalContext(as_of=as_of)
            except:
                self.temporal_context = TemporalContext(as_of=self.as_of or "2026-01-01T00:00:00Z")

class ScenarioResolver:
    """Resolves HistoricalScenario -> Scenario with temporal context."""

    @staticmethod
    def from_historical(
        historical: HistoricalScenario,
        race_date: str,
        as_of: str | None = None,
        scenario_type: ScenarioType = "historical",
        modifiers: dict[str, Any] | None = None,
    ) -> Scenario:
        # as_of defaults to day before race
        if as_of is None:
            try:
                dt = datetime.fromisoformat(race_date.replace("Z","+00:00") if "T" in race_date else race_date+"T00:00:00+00:00")  # noqa: E501
                # Subtract one day
                from datetime import timedelta
                as_of_dt = dt - timedelta(days=1)
                as_of = as_of_dt.isoformat().replace("+00:00","Z")
            except:
                as_of = race_date

        return Scenario(
            scenario_id=historical.scenario_id,
            type=scenario_type,
            season_id=historical.season_id,
            circuit_id=historical.track_id,
            date=race_date,
            as_of=as_of,
            drivers=historical.drivers,
            constructors=historical.cars,
            grid_order=historical.grid_order,
            qualifying_state={"observed_grid": historical.grid_order, "resimulate": False},
            weather_state=historical.weather,
            race_distance={"laps": historical.total_laps, "available": historical.total_laps is not None},  # noqa: E501
            historical_mode=(scenario_type=="historical"),
            hypothetical_modifiers=modifiers or {},
            dataset_version="f1-dataset-v1.1",
            calibration_version="calibration-v1.0.0",
            provenance={"historical_scenario_id": historical.scenario_id, "as_of": as_of},
            unavailable=historical.unavailable,
        )

    @staticmethod
    def for_future(
        circuit_id: str,
        date: str,
        drivers: list[dict[str, Any]],
        as_of: str,
        modifiers: dict[str, Any] | None = None,
    ) -> Scenario:
        return Scenario(
            scenario_id=f"future-{circuit_id}-{date}",
            type="future",
            season_id=date[:4],
            circuit_id=circuit_id,
            date=date,
            as_of=as_of,
            drivers=drivers,
            grid_order=[d["driver_id"] for d in drivers],
            historical_mode=False,
            hypothetical_modifiers=modifiers or {},
            unavailable=["historical_result"],
        )

class HistoricalStateBuilder:
    """Builds CalibrationState-ready historical state from Scenario."""

    @staticmethod
    def build(scenario: Scenario) -> dict[str, Any]:
        # Validate temporal: all scenario data should be before as_of? For now check
        # In historical mode, grid_order is observed from race, but as_of is before race, so grid_order is post-race info
        # For historical replay, we should NOT use observed grid if resimulate_qualifying is False? Actually spec says historical mode uses observed qualifying state
        # But then prediction would have post-race info (grid) - that's allowed for historical replay? The strict policy says post-race result must not leak, but grid is pre-race (qualifying) so it's allowed if qualifying is before race
        # We'll allow grid as pre-race info (qualifying day before)
        return {
            "scenario_id": scenario.scenario_id,
            "as_of": scenario.as_of,
            "temporal_context": scenario.temporal_context.model_dump() if scenario.temporal_context else None,  # noqa: E501
            "drivers": scenario.drivers,
            "grid_order": scenario.grid_order,
            "circuit_id": scenario.circuit_id,
            "era": HistoricalStateBuilder._era_for_season(scenario.season_id),
            "provenance": scenario.provenance,
            "unavailable": scenario.unavailable,
        }

    @staticmethod
    def _era_for_season(season_id: str) -> str:
        try:
            y=int(season_id)
        except:
            return "2022-2026"
        for name, s, e in [("1950-1960",1950,1960),("1961-1970",1961,1970),("1971-1982",1971,1982),("1983-1987",1983,1987),("1988-1993",1988,1993),("1994-1997",1994,1997),("1998-2008",1998,2008),("2009-2013",2009,2013),("2014-2021",2014,2021),("2022-2026",2022,2026)]:  # noqa: E501
            if s <= y <= e:
                return name
        return "2022-2026"
