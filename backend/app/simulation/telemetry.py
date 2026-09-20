"""Telemetry-ready data structures and sampling (Phase 8).

No real GPS coordinates are produced. Speed is an explicitly named
proxy derived from sector distance / sector time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.simulation.core.state import TelemetrySampling


@dataclass
class TelemetryRecord:
    """Single structured telemetry sample (serializable)."""

    lap: int
    sector: int  # -1 = lap aggregate
    driver_id: str
    position: int
    gap_ahead: float
    sector_time: float | None = None
    lap_time: float | None = None
    speed_proxy_kmh: float | None = None  # sector_distance / sector_time
    fuel_mass: float = 0.0
    ers_charge: float = 1.0
    ers_mode: str = "medium"
    tyre_compound: str = "medium"
    tyre_age: int = 0
    tyre_temp: float = 90.0
    track_wetness: float = 0.0
    drs_active: bool = False
    battle_state: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain serializable dict."""
        return asdict(self)


class TelemetrySampler:
    """Collects telemetry records according to the sampling level."""

    def __init__(self, sampling: TelemetrySampling = TelemetrySampling.OFF):
        self.sampling = sampling
        self.records: list[TelemetryRecord] = []

    def record(self, record: TelemetryRecord) -> None:
        """Append a record unless sampling is OFF."""
        if self.sampling == TelemetrySampling.OFF:
            return
        self.records.append(record)

    def record_sector(
        self,
        lap: int,
        sector: int,
        driver_id: str,
        position: int,
        gap_ahead: float,
        sector_time: float,
        sector_distance_km: float,
        driver_state: Any,
        track_wetness: float,
        battle_state: str | None = None,
    ) -> None:
        """Record a per-sector sample (SECTOR and FULL levels)."""
        if self.sampling not in (TelemetrySampling.SECTOR, TelemetrySampling.FULL):
            return
        speed = (sector_distance_km / sector_time * 3600.0) if sector_time > 0 else None
        self.record(TelemetryRecord(
            lap=lap,
            sector=sector,
            driver_id=driver_id,
            position=position,
            gap_ahead=gap_ahead,
            sector_time=sector_time,
            speed_proxy_kmh=speed,
            fuel_mass=driver_state.fuel_mass,
            ers_charge=driver_state.ers_charge,
            ers_mode=driver_state.ers_mode,
            tyre_compound=driver_state.tyre_compound.value if hasattr(
                driver_state.tyre_compound, "value") else str(driver_state.tyre_compound),
            tyre_age=driver_state.tyre_age,
            tyre_temp=driver_state.tyre_temp,
            track_wetness=track_wetness,
            drs_active=driver_state.drs_active,
            battle_state=battle_state,
        ))

    def record_lap(
        self,
        lap: int,
        driver_id: str,
        position: int,
        gap_ahead: float,
        lap_time: float,
        driver_state: Any,
        track_wetness: float,
    ) -> None:
        """Record a per-lap aggregate sample (LAP and FULL levels)."""
        if self.sampling not in (TelemetrySampling.LAP, TelemetrySampling.FULL):
            return
        self.record(TelemetryRecord(
            lap=lap,
            sector=-1,
            driver_id=driver_id,
            position=position,
            gap_ahead=gap_ahead,
            lap_time=lap_time,
            fuel_mass=driver_state.fuel_mass,
            ers_charge=driver_state.ers_charge,
            ers_mode=driver_state.ers_mode,
            tyre_compound=driver_state.tyre_compound.value if hasattr(
                driver_state.tyre_compound, "value") else str(driver_state.tyre_compound),
            tyre_age=driver_state.tyre_age,
            tyre_temp=driver_state.tyre_temp,
            track_wetness=track_wetness,
            drs_active=driver_state.drs_active,
        ))

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return all records as plain dicts."""
        return [r.to_dict() for r in self.records]
