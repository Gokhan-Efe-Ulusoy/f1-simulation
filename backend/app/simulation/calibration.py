"""Calibration profiles for future historical-data fitting (Phase 8).

No 1950-2026 data is populated here. These are typed extension points:
a profile holds named multipliers that model code can query. An empty
profile is the identity (no adjustment), so default behaviour is unchanged.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TrackCalibration(BaseModel):
    """Per-track calibration multipliers (identity by default)."""

    track_id: str = "default"
    overtaking_difficulty_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)
    dirty_air_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)
    degradation_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)
    drs_effect_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)

    model_config = {"use_enum_values": True}


class DriverCalibration(BaseModel):
    """Per-driver calibration offsets (identity by default)."""

    driver_id: str = "default"
    start_performance_offset: float = Field(default=0.0, ge=-20.0, le=20.0)
    overtaking_offset: float = Field(default=0.0, ge=-20.0, le=20.0)
    defending_offset: float = Field(default=0.0, ge=-20.0, le=20.0)
    mistake_rate_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)

    model_config = {"use_enum_values": True}


class CarCalibration(BaseModel):
    """Per-car calibration multipliers (identity by default)."""

    car_id: str = "default"
    straight_line_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    braking_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    traction_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)

    model_config = {"use_enum_values": True}


class EraCalibration(BaseModel):
    """Era-wide calibration bundle (identity by default)."""

    era_id: str = "2024"
    fuel_effect_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)
    tyre_wear_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)
    incident_multiplier: float = Field(default=1.0, ge=0.1, le=3.0)

    model_config = {"use_enum_values": True}


class CalibrationProfile(BaseModel):
    """Container binding all calibration dimensions."""

    profile_id: str = "default"
    tracks: dict[str, TrackCalibration] = Field(default_factory=dict)
    drivers: dict[str, DriverCalibration] = Field(default_factory=dict)
    cars: dict[str, CarCalibration] = Field(default_factory=dict)
    era: EraCalibration = Field(default_factory=EraCalibration)

    model_config = {"use_enum_values": True}

    def track_calibration(self, track_id: str) -> TrackCalibration:
        """Return track calibration (identity if uncalibrated)."""
        return self.tracks.get(track_id, TrackCalibration(track_id=track_id))

    def driver_calibration(self, driver_id: str) -> DriverCalibration:
        """Return driver calibration (identity if uncalibrated)."""
        return self.drivers.get(driver_id, DriverCalibration(driver_id=driver_id))

    def car_calibration(self, car_id: str) -> CarCalibration:
        """Return car calibration (identity if uncalibrated)."""
        return self.cars.get(car_id, CarCalibration(car_id=car_id))
