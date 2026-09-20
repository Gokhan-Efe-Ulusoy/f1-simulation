"""Canonical historical F1 data models (Phase 9A).

Conventions (see docs/phase9-historical-data.md):
- Stable string IDs (``driver_id``, ``race_id``, ...); display names are
  never primary keys. Historical name variants live in ``aliases``.
- Entity (driver/constructor/circuit) is separate from event (race).
- Missing information is ``None`` (unavailable), never fabricated.
- All numerics carry explicit units in the field name.
- Times are ISO-8601 strings; durations are ``*_seconds`` floats.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FeatureType = Literal["observed", "derived", "inferred", "simulated"]


class DataSource(BaseModel):
    """A registered data provider (no data is fetched by registering)."""

    provider: str = Field(description="Provider name, e.g. 'jolpica'")
    source_id: str = Field(description="Stable source identifier")
    base_url: str = Field(default="", description="API endpoint or archive URL")
    coverage_start: int = Field(default=1950, ge=1950, le=2026)
    coverage_end: int = Field(default=2026, ge=1950, le=2026)
    license_notes: str = Field(default="", description="Known usage constraints")
    parser_version: str = Field(default="0.1.0")

    model_config = {"use_enum_values": True}


class DataProvenance(BaseModel):
    """Traceability record attached to every imported record."""

    source_provider: str
    source_record_id: str = ""
    source_url: str = ""
    retrieved_at: str = ""  # ISO-8601 UTC
    parser_version: str = "0.1.0"
    raw_file_hash: str = ""  # sha256 of the raw payload when practical
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    transformation_chain: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}

    def extended(self, step: str) -> DataProvenance:
        """Return a copy with one more transformation step appended."""
        clone = self.model_copy()
        clone.transformation_chain = [*self.transformation_chain, step]
        return clone


class DataAvailability(BaseModel):
    """Explicit availability metadata for one field/dimension."""

    field: str
    available: bool
    source: str = ""
    coverage_start: int | None = None
    coverage_end: int | None = None
    resolution: str = ""  # e.g. "race", "lap", "sector", "telemetry"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = {"use_enum_values": True}


class DataQualityReport(BaseModel):
    """Automated validation output for a dataset version."""

    dataset_version: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    source_conflicts: int = 0

    model_config = {"use_enum_values": True}

    @property
    def is_clean(self) -> bool:
        """True when no errors were recorded."""
        return not self.errors


class HistoricalDriver(BaseModel):
    """Canonical driver entity (identity, not results)."""

    driver_id: str
    full_name: str
    aliases: list[str] = Field(default_factory=list)
    nationality: str = ""
    date_of_birth: str = ""  # ISO date, "" when unknown
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalConstructor(BaseModel):
    """Canonical constructor/team entity (ownership/name eras via aliases)."""

    constructor_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    nationality: str = ""
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalEngine(BaseModel):
    """Canonical power-unit entity."""

    engine_id: str
    manufacturer: str
    aliases: list[str] = Field(default_factory=list)
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalCar(BaseModel):
    """Canonical chassis entity (constructor + season + engine link)."""

    car_id: str
    constructor_id: str
    season_id: str
    chassis_name: str = ""
    engine_id: str = ""
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalCircuit(BaseModel):
    """Canonical circuit entity (venue, not event)."""

    circuit_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    country: str = ""
    locality: str = ""
    length_km: float | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalSeason(BaseModel):
    """Canonical season entity."""

    season_id: str  # e.g. "2024"
    year: int = Field(ge=1950, le=2026)
    rounds: int = Field(default=0, ge=0)
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalRace(BaseModel):
    """Canonical race event (distinct from circuit and season)."""

    race_id: str  # e.g. "2024-bahrain"
    season_id: str
    round: int = Field(ge=1)
    official_name: str = ""
    circuit_id: str = ""
    date: str = ""  # ISO date
    scheduled_laps: int | None = None
    scheduled_distance_km: float | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalSession(BaseModel):
    """Canonical session within a race event (practice/qualifying/race...)."""

    session_id: str  # e.g. "2024-bahrain:race"
    race_id: str
    session_type: str = ""  # normalized: practice_1, qualifying, sprint, race, ...
    date: str = ""
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalResult(BaseModel):
    """Canonical race classification entry (nulls = unavailable)."""

    result_id: str  # e.g. "2024-bahrain:VER"
    race_id: str
    driver_id: str
    constructor_id: str = ""
    car_id: str = ""
    grid_position: int | None = None
    final_position: int | None = None  # None = unclassified/DNF detail in status
    status: str = ""  # e.g. "finished", "retired", "disqualified"
    laps_completed: int | None = None
    total_time_seconds: float | None = None
    time_gap_seconds: float | None = None  # to winner
    points: float | None = None
    fastest_lap_seconds: float | None = None
    fastest_lap_number: int | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalQualifyingResult(BaseModel):
    """Canonical qualifying classification entry."""

    result_id: str
    race_id: str
    driver_id: str
    constructor_id: str = ""
    final_grid_position: int | None = None
    q1_time_seconds: float | None = None
    q2_time_seconds: float | None = None
    q3_time_seconds: float | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalLap(BaseModel):
    """Canonical lap record (modern resolution only)."""

    lap_id: str  # e.g. "2024-bahrain:VER:12"
    race_id: str
    driver_id: str
    lap_number: int = Field(ge=1)
    lap_time_seconds: float | None = None
    position: int | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalSector(BaseModel):
    """Canonical sector record (modern resolution only)."""

    sector_id: str  # e.g. "2024-bahrain:VER:12:S1"
    lap_id: str
    sector_index: int = Field(ge=0)
    sector_time_seconds: float | None = None
    speed_kph: float | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalPitStop(BaseModel):
    """Canonical pit-stop record."""

    pit_stop_id: str
    race_id: str
    driver_id: str
    lap_number: int | None = None
    stationary_time_seconds: float | None = None
    total_time_loss_seconds: float | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalTyreStint(BaseModel):
    """Canonical tyre-stint record."""

    stint_id: str
    race_id: str
    driver_id: str
    compound: str = ""  # normalized compound name
    stint_number: int | None = None
    laps_on_compound: int | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalWeatherObservation(BaseModel):
    """Canonical weather observation (units explicit)."""

    observation_id: str
    race_id: str
    air_temperature_c: float | None = None
    track_temperature_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_kph: float | None = None
    rainfall_mm_per_hr: float | None = None
    condition: str = ""
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalChampionshipStanding(BaseModel):
    """Canonical championship standing entry."""

    standing_id: str  # e.g. "2024:drivers:VER:after-03"
    season_id: str
    category: str = ""  # "drivers" | "constructors"
    participant_id: str = ""  # driver_id or constructor_id
    points: float | None = None
    position: int | None = None
    after_round: int | None = None
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}


class HistoricalRegulation(BaseModel):
    """Canonical regulation metadata for a season (high-confidence first)."""

    regulation_id: str  # e.g. "2024:qualifying-format"
    season_id: str
    domain: str = ""  # qualifying_format, points_system, refuelling, ...
    value: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: DataProvenance | None = None

    model_config = {"use_enum_values": True}
