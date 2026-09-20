from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import BaseModel, Field


class TyreCompound(str, Enum):
    """Tyre compound types."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class CompoundType(str, Enum):
    """Compound type classification for strategy."""
    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class TyreVisualCompound(str, Enum):
    """Visual compound for TV graphics."""

    RED = "red"      # Soft
    YELLOW = "yellow"  # Medium
    WHITE = "white"    # Hard
    GREEN = "green"    # Intermediate
    BLUE = "blue"      # Wet


class TyreSpec(BaseModel):
    """Specification for a tyre compound."""

    compound: TyreCompound
    visual_compound: TyreVisualCompound

    # Performance (relative to medium = 1.0)
    # Lower = faster
    base_pace_factor: float = Field(default=1.0, gt=0)
    # Soft ~0.97, Medium ~1.0, Hard ~1.03, Inter ~1.08, Wet ~1.15

    # Degradation
    degradation_rate: float = Field(default=0.05, ge=0.01, le=0.30)  # sec/lap base rate
    degradation_exponent: float = Field(default=1.2, ge=1.0, le=2.5)  # Non-linear wear
    # pace_loss(age) = degradation_rate * age^degradation_exponent

    # Wear limits
    max_life_laps: int = Field(default=30, ge=5, le=60)  # Laps to 100% wear
    cliff_threshold: float = Field(default=0.85, ge=0.5, le=1.0)  # Wear % where cliff starts
    cliff_severity: float = Field(default=2.0, ge=1.0, le=5.0)  # Multiplier after cliff

    # Warm-up
    warmup_laps: int = Field(default=1, ge=1, le=4)  # Laps to reach optimal temp
    warmup_pace_penalty: float = Field(default=0.8, ge=0.2, le=2.0)  # sec per lap cold
    optimal_temp_min: float = Field(default=85, ge=60, le=100)  # Celsius
    optimal_temp_max: float = Field(default=110, ge=90, le=130)

    # Temperature sensitivity
    temp_sensitivity: float = Field(default=0.02, ge=0.005, le=0.05)  # sec per degree outside window  # noqa: E501
    overheating_threshold: float = Field(default=120, ge=110, le=140)
    overheating_penalty: float = Field(default=0.05, ge=0.01, le=0.20)  # sec per degree over

    # Weather suitability (0-1, 1 = perfect)
    dry_suitability: float = Field(default=1.0, ge=0, le=1)
    damp_suitability: float = Field(default=0.3, ge=0, le=1)
    wet_suitability: float = Field(default=0.0, ge=0, le=1)
    standing_water_suitability: float = Field(default=0.0, ge=0, le=1)

    # Grip characteristics
    peak_grip: float = Field(default=1.0, ge=0.5, le=1.2)  # Relative peak grip
    grip_drop_off: float = Field(default=0.15, ge=0.05, le=0.40)  # Grip loss at 100% wear

    # Pressure
    min_pressure_psi: float = Field(default=20.0, ge=15, le=25)
    max_pressure_psi: float = Field(default=25.0, ge=20, le=30)
    optimal_pressure_psi: float = Field(default=22.0, ge=18, le=24)

    # Stint length estimates
    typical_stint_laps: dict[str, int] = Field(default_factory=dict)
    # {"low_fuel": 25, "high_fuel": 20, "qualifying": 3}

    model_config = {"use_enum_values": True}

    def get_pace_factor(self, age_laps: int, wear: float, temp: float,
                       weather: str = "dry", fuel_mass: float = 50) -> float:
        """Get pace factor for current tyre state.
        
        Returns multiplier where 1.0 = base pace, >1.0 = slower.
        """
        # Base pace
        pace = self.base_pace_factor

        # Degradation
        if age_laps > 0:
            deg = self.degradation_rate * (age_laps ** self.degradation_exponent)
            # Cliff effect
            if wear >= self.cliff_threshold:
                cliff_progress = (wear - self.cliff_threshold) / (1.0 - self.cliff_threshold)
                deg *= 1.0 + cliff_progress * (self.cliff_severity - 1.0)
            pace += deg

        # Temperature
        if temp < self.optimal_temp_min:
            pace += (self.optimal_temp_min - temp) * self.warmup_pace_penalty / self.warmup_laps
        elif temp > self.optimal_temp_max:
            pace += (temp - self.optimal_temp_max) * self.overheating_penalty

        # Weather suitability
        weather_suit = self.get_weather_suitability(weather)
        if weather_suit < 1.0:
            pace += (1.0 - weather_suit) * 2.0  # Up to 2s penalty

        # Fuel effect (tyres work harder with more fuel)
        fuel_factor = 1.0 + (fuel_mass / 110) * 0.02  # Up to 2% slower at full fuel
        pace *= fuel_factor

        return pace

    def get_weather_suitability(self, weather: str) -> float:
        """Get weather suitability factor."""
        weather_map = {
            "dry": self.dry_suitability,
            "damp": self.damp_suitability,
            "light_rain": self.wet_suitability,
            "heavy_rain": self.standing_water_suitability,
            "wet": self.wet_suitability,
            "intermediate": self.wet_suitability,
        }
        return weather_map.get(weather, self.dry_suitability)

    def get_degradation_per_lap(self, age_laps: int, wear: float) -> float:
        """Get instantaneous degradation rate at given age/wear."""
        base = self.degradation_rate * self.degradation_exponent * (age_laps ** (self.degradation_exponent - 1))  # noqa: E501
        if wear >= self.cliff_threshold:
            cliff_progress = (wear - self.cliff_threshold) / (1.0 - self.cliff_threshold)
            base *= 1.0 + cliff_progress * (self.cliff_severity - 1.0)
        return base

    def estimate_stint_length(self, track_roughness: float = 1.0,
                             fuel_correction: float = 1.0) -> int:
        """Estimate optimal stint length in laps."""
        base = self.max_life_laps
        # Adjust for track roughness
        base /= track_roughness
        # Adjust for fuel (heavier = more wear)
        base /= fuel_correction
        return max(5, min(self.max_life_laps, int(base)))

    @property
    def compound_type(self) -> CompoundType:
        """Get compound type for strategy classification."""
        mapping = {
            TyreCompound.SOFT: CompoundType.SOFT,
            TyreCompound.MEDIUM: CompoundType.MEDIUM,
            TyreCompound.HARD: CompoundType.HARD,
            TyreCompound.INTERMEDIATE: CompoundType.INTERMEDIATE,
            TyreCompound.WET: CompoundType.WET,
        }
        return mapping.get(self.compound, CompoundType.MEDIUM)


class TyreState(BaseModel):
    """Runtime state of a tyre set."""

    compound: TyreCompound
    set_id: str  # Unique identifier for this set

    # Age and wear
    age_laps: int = 0
    wear: float = 0.0  # 0-1

    # Temperature
    temp_fl: float = 90.0  # Front left
    temp_fr: float = 90.0  # Front right
    temp_rl: float = 90.0  # Rear left
    temp_rr: float = 90.0  # Rear right

    # Pressure
    pressure_fl: float = 22.0
    pressure_fr: float = 22.0
    pressure_rl: float = 22.0
    pressure_rr: float = 22.0

    # Damage
    flatspot_severity: float = 0.0  # 0-1
    cuts: int = 0
    puncture_risk: float = 0.0  # 0-1 per lap

    # History
    laps_done: list[int] = Field(default_factory=list)  # Lap numbers when used
    stint_start_lap: int = 0
    stint_lap: int = 0

    model_config = {"use_enum_values": True}

    @property
    def avg_temp(self) -> float:
        return (self.temp_fl + self.temp_fr + self.temp_rl + self.temp_rr) / 4

    @property
    def avg_pressure(self) -> float:
        return (self.pressure_fl + self.pressure_fr + self.pressure_rl + self.pressure_rr) / 4

    def is_worn_out(self) -> bool:
        return self.wear >= 1.0

    def is_in_optimal_window(self, spec: TyreSpec) -> bool:
        return spec.optimal_temp_min <= self.avg_temp <= spec.optimal_temp_max

    def get_grip_level(self, spec: TyreSpec) -> float:
        """Get current grip level (0-1)."""
        base_grip = spec.peak_grip * (1.0 - self.wear * spec.grip_drop_off)
        # Temperature effect
        if self.avg_temp < spec.optimal_temp_min:
            base_grip *= 0.7 + 0.3 * (self.avg_temp / spec.optimal_temp_min)
        elif self.avg_temp > spec.optimal_temp_max:
            overheat = (self.avg_temp - spec.optimal_temp_max) / 20
            base_grip *= max(0.5, 1.0 - overheat * 0.2)
        # Flatspot
        base_grip *= (1.0 - self.flatspot_severity * 0.3)
        return max(0.1, base_grip)


# Standard F1 tyre specifications (approximate 2024 Pirelli specs)
@lru_cache(maxsize=1)
def get_standard_tyre_specs() -> dict[TyreCompound, TyreSpec]:
    """Get standard F1 tyre specifications (cached pure function)."""
    return {
        TyreCompound.SOFT: TyreSpec(
            compound=TyreCompound.SOFT,
            visual_compound=TyreVisualCompound.RED,
            base_pace_factor=0.97,
            degradation_rate=0.07,
            degradation_exponent=1.3,
            max_life_laps=20,
            cliff_threshold=0.80,
            cliff_severity=3.0,
            warmup_laps=1,
            warmup_pace_penalty=0.5,
            optimal_temp_min=90,
            optimal_temp_max=110,
            temp_sensitivity=0.025,
            overheating_threshold=115,
            overheating_penalty=0.08,
            dry_suitability=1.0,
            damp_suitability=0.1,
            wet_suitability=0.0,
            standing_water_suitability=0.0,
            peak_grip=1.15,
            grip_drop_off=0.25,
            min_pressure_psi=20.0,
            max_pressure_psi=23.0,
            optimal_pressure_psi=21.5,
            typical_stint_laps={"low_fuel": 18, "high_fuel": 14, "qualifying": 3},
        ),
        TyreCompound.MEDIUM: TyreSpec(
            compound=TyreCompound.MEDIUM,
            visual_compound=TyreVisualCompound.YELLOW,
            base_pace_factor=1.00,
            degradation_rate=0.045,
            degradation_exponent=1.2,
            max_life_laps=30,
            cliff_threshold=0.85,
            cliff_severity=2.0,
            warmup_laps=2,
            warmup_pace_penalty=0.6,
            optimal_temp_min=85,
            optimal_temp_max=115,
            temp_sensitivity=0.020,
            overheating_threshold=120,
            overheating_penalty=0.05,
            dry_suitability=1.0,
            damp_suitability=0.3,
            wet_suitability=0.0,
            standing_water_suitability=0.0,
            peak_grip=1.00,
            grip_drop_off=0.15,
            min_pressure_psi=20.5,
            max_pressure_psi=24.0,
            optimal_pressure_psi=22.0,
            typical_stint_laps={"low_fuel": 28, "high_fuel": 22, "qualifying": 5},
        ),
        TyreCompound.HARD: TyreSpec(
            compound=TyreCompound.HARD,
            visual_compound=TyreVisualCompound.WHITE,
            base_pace_factor=1.03,
            degradation_rate=0.03,
            degradation_exponent=1.15,
            max_life_laps=40,
            cliff_threshold=0.90,
            cliff_severity=1.5,
            warmup_laps=3,
            warmup_pace_penalty=0.8,
            optimal_temp_min=80,
            optimal_temp_max=120,
            temp_sensitivity=0.015,
            overheating_threshold=125,
            overheating_penalty=0.03,
            dry_suitability=1.0,
            damp_suitability=0.5,
            wet_suitability=0.0,
            standing_water_suitability=0.0,
            peak_grip=0.90,
            grip_drop_off=0.10,
            min_pressure_psi=21.0,
            max_pressure_psi=25.0,
            optimal_pressure_psi=22.5,
            typical_stint_laps={"low_fuel": 35, "high_fuel": 28, "qualifying": 8},
        ),
        TyreCompound.INTERMEDIATE: TyreSpec(
            compound=TyreCompound.INTERMEDIATE,
            visual_compound=TyreVisualCompound.GREEN,
            base_pace_factor=1.08,
            degradation_rate=0.06,
            degradation_exponent=1.1,
            max_life_laps=25,
            cliff_threshold=0.75,
            cliff_severity=2.5,
            warmup_laps=1,
            warmup_pace_penalty=0.3,
            optimal_temp_min=60,
            optimal_temp_max=90,
            temp_sensitivity=0.02,
            overheating_threshold=110,
            overheating_penalty=0.05,
            dry_suitability=0.0,
            damp_suitability=1.0,
            wet_suitability=0.7,
            standing_water_suitability=0.2,
            peak_grip=0.85,
            grip_drop_off=0.20,
            min_pressure_psi=19.0,
            max_pressure_psi=22.0,
            optimal_pressure_psi=20.5,
            typical_stint_laps={"low_fuel": 20, "high_fuel": 16, "qualifying": 4},
        ),
        TyreCompound.WET: TyreSpec(
            compound=TyreCompound.WET,
            visual_compound=TyreVisualCompound.BLUE,
            base_pace_factor=1.15,
            degradation_rate=0.05,
            degradation_exponent=1.05,
            max_life_laps=30,
            cliff_threshold=0.70,
            cliff_severity=2.0,
            warmup_laps=1,
            warmup_pace_penalty=0.2,
            optimal_temp_min=60,
            optimal_temp_max=90,
            temp_sensitivity=0.015,
            overheating_threshold=110,
            overheating_penalty=0.04,
            dry_suitability=0.0,
            damp_suitability=0.5,
            wet_suitability=1.0,
            standing_water_suitability=1.0,
            peak_grip=0.75,
            grip_drop_off=0.15,
            min_pressure_psi=18.0,
            max_pressure_psi=21.0,
            optimal_pressure_psi=19.5,
            typical_stint_laps={"low_fuel": 25, "high_fuel": 20, "qualifying": 5},
        ),
    }


def get_compound_for_weather(weather: str) -> list[TyreCompound]:
    """Get suitable compounds for weather condition."""
    if weather in ("dry",):
        return [TyreCompound.SOFT, TyreCompound.MEDIUM, TyreCompound.HARD]
    elif weather in ("damp", "light_rain"):
        return [TyreCompound.INTERMEDIATE, TyreCompound.MEDIUM]
    elif weather in ("wet", "heavy_rain"):
        return [TyreCompound.WET, TyreCompound.INTERMEDIATE]


# Default compounds dict for strategy engine
DEFAULT_COMPOUNDS = get_standard_tyre_specs()
