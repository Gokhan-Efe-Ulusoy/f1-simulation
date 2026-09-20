"""Models for Phase 27 lap-time decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class IdentifiabilityTier(str, Enum):
    CALIBRATED = "CALIBRATED"
    LIMITED = "LIMITED"
    PRIOR_ONLY = "PRIOR_ONLY"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    REJECTED = "REJECTED"
    ASSOCIATIONAL = "ASSOCIATIONAL"


class LapQuality(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    PIT_LAP = "pit-lap"
    FORMATION = "formation"
    SAFETY_CAR = "safety-car/neutralised"
    RED_FLAG = "red-flag/frozen"
    OUTLIER = "outlier"
    MISSING = "missing"


@dataclass(frozen=True)
class LapRecord:
    race_id: str
    season: int
    circuit: str
    driver_number: int
    driver_id: str
    constructor: str
    lap_number: int
    stint_lap: int
    compound: str | None
    tyre_age: int | None
    lap_time_seconds: float | None
    is_pit_in: bool = False
    is_pit_out: bool = False
    race_control_flag: str = "GREEN"
    is_wet: bool = False
    air_temp: float | None = None
    track_temp: float | None = None
    rainfall: float | None = None
    as_of: str = ""


@dataclass
class DecompositionComponents:
    """Conceptual decomposition, only fitted if identifiable."""
    circuit_baseline: float = 0.0
    driver_effect: float = 0.0
    constructor_effect: float = 0.0
    tyre_effect: float = 0.0  # NON_IDENTIFIABLE currently
    race_progression_effect: float = 0.0  # ASSOCIATIONAL, not fuel
    neutralisation_effect: float = 0.0  # LIMITED/PRIOR_ONLY
    pit_context: float = 0.0  # mean total only
    weather_effect: float = 0.0  # LIMITED/PRIOR_ONLY
    residual: float = 0.0
    total_predicted: float = 0.0

    def to_dict(self):
        return {
            "circuit_baseline": self.circuit_baseline,
            "driver_effect": self.driver_effect,
            "constructor_effect": self.constructor_effect,
            "tyre_effect": self.tyre_effect,
            "race_progression_effect": self.race_progression_effect,
            "neutralisation_effect": self.neutralisation_effect,
            "pit_context": self.pit_context,
            "weather_effect": self.weather_effect,
            "residual": self.residual,
            "total_predicted": self.total_predicted,
        }


@dataclass
class QualityCounts:
    valid: int = 0
    invalid: int = 0
    pit_lap: int = 0
    formation: int = 0
    safety_car: int = 0
    red_flag: int = 0
    outlier: int = 0
    missing: int = 0
    total: int = 0
