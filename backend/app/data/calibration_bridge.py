"""Calibration bridge: fitted profiles with uncertainty (Phase 9E).

Extends (never replaces) the Phase 8 ``CalibrationProfile`` identity
multipliers with per-parameter uncertainty, dataset linkage, fitting
method and calibration date. ``to_simulation_profile()`` projects back
to the engine-native shape.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.simulation.calibration import CalibrationProfile


class CalibratedParameter(BaseModel):
    """One fitted parameter with full calibration metadata."""

    name: str
    value: float
    uncertainty: float = Field(default=0.0, ge=0.0)
    source_dataset: str = ""
    fitting_method: str = ""
    calibration_date: str = ""
    model_version: str = ""
    dataset_version: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = {"use_enum_values": True}


class TrackCalibrationProfile(BaseModel):
    """Fitted track profile (named multipliers + metadata)."""

    track_id: str
    parameters: dict[str, CalibratedParameter] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def multiplier(self, name: str) -> float:
        """Parameter value or identity 1.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 1.0


class DriverCalibrationProfile(BaseModel):
    """Fitted driver profile (offsets + multipliers + metadata)."""

    driver_id: str
    parameters: dict[str, CalibratedParameter] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def offset(self, name: str) -> float:
        """Offset value or identity 0.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 0.0

    def multiplier(self, name: str) -> float:
        """Multiplier value or identity 1.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 1.0


class CarCalibrationProfile(BaseModel):
    """Fitted car profile (named multipliers + metadata)."""

    car_id: str
    parameters: dict[str, CalibratedParameter] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def multiplier(self, name: str) -> float:
        """Parameter value or identity 1.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 1.0


class ConstructorCalibrationProfile(BaseModel):
    """Fitted constructor profile (named multipliers + metadata)."""

    constructor_id: str
    parameters: dict[str, CalibratedParameter] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def multiplier(self, name: str) -> float:
        """Parameter value or identity 1.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 1.0


class EraCalibrationProfile(BaseModel):
    """Fitted era profile (named multipliers + metadata)."""

    era_id: str
    parameters: dict[str, CalibratedParameter] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def multiplier(self, name: str) -> float:
        """Parameter value or identity 1.0 when unfitted."""
        param = self.parameters.get(name)
        return param.value if param is not None else 1.0


class FittedCalibrationSet(BaseModel):
    """A full fitted set that projects onto the engine-native profile."""

    set_id: str = "default"
    tracks: dict[str, TrackCalibrationProfile] = Field(default_factory=dict)
    drivers: dict[str, DriverCalibrationProfile] = Field(default_factory=dict)
    cars: dict[str, CarCalibrationProfile] = Field(default_factory=dict)
    constructors: dict[str, ConstructorCalibrationProfile] = Field(default_factory=dict)
    era: EraCalibrationProfile | None = None

    model_config = {"use_enum_values": True}

    def to_simulation_profile(self) -> CalibrationProfile:
        """Project onto the Phase 8 engine-native CalibrationProfile."""
        from app.simulation.calibration import (
            CarCalibration,
            DriverCalibration,
            EraCalibration,
            TrackCalibration,
        )

        profile = CalibrationProfile(profile_id=self.set_id)
        for track_id, fitted_track in self.tracks.items():
            profile.tracks[track_id] = TrackCalibration(
                track_id=track_id,
                overtaking_difficulty_multiplier=fitted_track.multiplier(
                    "overtaking_difficulty_multiplier"),
                dirty_air_multiplier=fitted_track.multiplier("dirty_air_multiplier"),
                degradation_multiplier=fitted_track.multiplier("degradation_multiplier"),
                drs_effect_multiplier=fitted_track.multiplier("drs_effect_multiplier"),
            )
        for driver_id, fitted_driver in self.drivers.items():
            profile.drivers[driver_id] = DriverCalibration(
                driver_id=driver_id,
                start_performance_offset=fitted_driver.offset("start_performance_offset"),
                overtaking_offset=fitted_driver.offset("overtaking_offset"),
                defending_offset=fitted_driver.offset("defending_offset"),
                mistake_rate_multiplier=fitted_driver.multiplier("mistake_rate_multiplier"),
            )
        for car_id, fitted_car in self.cars.items():
            profile.cars[car_id] = CarCalibration(
                car_id=car_id,
                straight_line_multiplier=fitted_car.multiplier("straight_line_multiplier"),
                braking_multiplier=fitted_car.multiplier("braking_multiplier"),
                traction_multiplier=fitted_car.multiplier("traction_multiplier"),
            )
        if self.era is not None:
            profile.era = EraCalibration(
                era_id=self.era.era_id,
                fuel_effect_multiplier=self.era.multiplier("fuel_effect_multiplier"),
                tyre_wear_multiplier=self.era.multiplier("tyre_wear_multiplier"),
                incident_multiplier=self.era.multiplier("incident_multiplier"),
            )
        return profile
