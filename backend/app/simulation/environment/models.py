from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TrackWetnessZone(str, Enum):
    """Track zones for wetness tracking."""
    RACING_LINE = "racing_line"
    OFF_LINE = "off_line"
    PIT_LANE = "pit_lane"


@dataclass
class SectorWetness:
    """Wetness state for a single sector."""
    sector: int
    racing_line_wetness: float = 0.0  # 0 = dry, 1 = soaking
    off_line_wetness: float = 0.0
    rubber_build_up: float = 0.0  # 0 = green, 1 = fully rubbered

    def get_effective_wetness(self, on_racing_line: bool) -> float:
        """Get effective wetness for a car on/off racing line."""
        if on_racing_line:
            return self.racing_line_wetness
        return self.off_line_wetness


class TrackWetnessModel(BaseModel):
    """Model for track wetness evolution per sector."""

    # Track reference
    track: Any = None

    # Sector wetness states
    sector_wetness: dict[int, SectorWetness] = field(default_factory=dict)

    # Drying parameters
    base_drying_rate: float = Field(default=0.02, ge=0.005, le=0.1)  # per lap
    racing_line_drying_multiplier: float = Field(default=1.5, ge=1.0, le=3.0)
    off_line_wetness_multiplier: float = Field(default=1.2, ge=1.0, le=2.0)
    wind_drying_factor: float = Field(default=0.02, ge=0, le=0.1)  # per m/s
    temp_drying_factor: float = Field(default=0.01, ge=0, le=0.05)  # per degree above 20C

    # Wetting parameters
    rain_accumulation_rate: float = Field(default=0.01, ge=0.001, le=0.05)  # per mm/hr

    # Random provider
    _rng: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def initialize(self, track: Any, rng: Any) -> None:
        """Initialize the model with track and RNG."""
        self.track = track
        self._rng = rng

        # Initialize sector wetness
        n_sectors = track.number_of_sectors
        for s in range(n_sectors):
            self.sector_wetness[s] = SectorWetness(sector=s)

    def step(
        self,
        current_weather: Any,
        cars_on_track: int = 20,
    ) -> dict[int, SectorWetness]:
        """Evolve track wetness by one lap."""
        if self._rng is None:
            raise RuntimeError("TrackWetnessModel not initialized with RNG")

        for _sector, wetness in self.sector_wetness.items():
            # Rain accumulation
            if current_weather.is_rain():
                precip = current_weather.precipitation_rate
                accumulation = precip * self.rain_accumulation_rate
                wetness.racing_line_wetness = min(1.0, wetness.racing_line_wetness + accumulation)
                wetness.off_line_wetness = min(1.0, wetness.off_line_wetness + accumulation * 1.2)

            # Drying
            else:
                if wetness.racing_line_wetness > 0 or wetness.off_line_wetness > 0:
                    # Base drying rate
                    dry_rate = self.base_drying_rate

                    # Wind effect
                    dry_rate *= (1 + current_weather.wind_speed * self.wind_drying_factor)

                    # Temperature effect
                    if current_weather.track_temperature > 20:
                        dry_rate *= (1 + (current_weather.track_temperature - 20) * self.temp_drying_factor)  # noqa: E501

                    # Cars on track accelerate drying (rubber displaces water)
                    traffic_factor = min(1.5, cars_on_track / 20)

                    # Racing line dries faster
                    racing_line_rate = dry_rate * self.racing_line_drying_multiplier * traffic_factor  # noqa: E501
                    off_line_rate = dry_rate * traffic_factor

                    # Apply drying
                    wetness.racing_line_wetness = max(0.0, wetness.racing_line_wetness - racing_line_rate)  # noqa: E501
                    wetness.off_line_wetness = max(0.0, wetness.off_line_wetness - off_line_rate)

            # Rubber build-up (cars on track)
            if cars_on_track > 0:
                rubber_rate = 0.01 * (cars_on_track / 20)
                wetness.rubber_build_up = min(1.0, wetness.rubber_build_up + rubber_rate)

        return self.sector_wetness.copy()

    def get_effective_wetness(self, sector: int, on_racing_line: bool) -> float:
        """Get effective wetness for a sector and line."""
        if sector not in self.sector_wetness:
            return 0.0
        return self.sector_wetness[sector].get_effective_wetness(on_racing_line)

    def get_drying_line_info(self) -> dict[int, Any]:
        """Get information about drying line state for strategy."""
        info = {}
        for sector, wetness in self.sector_wetness.items():
            info[sector] = {
                "racing_line_wetness": wetness.racing_line_wetness,
                "off_line_wetness": wetness.off_line_wetness,
                "delta": wetness.off_line_wetness - wetness.racing_line_wetness,
                "rubber_build_up": wetness.rubber_build_up,
            }
        return info


class TyreCrossoverAssessment(BaseModel):
    """Assessment of tyre compound crossover."""

    recommended_compound: str
    confidence: float  # 0-1
    expected_delta: float  # sec/lap vs current compound
    reason: str
    crossover_lap: int | None = None  # Lap when crossover becomes favorable


class TyreCrossoverModel(BaseModel):
    """Model for detecting tyre compound crossover points."""

    # Crossover thresholds (track wetness)
    slick_to_intermediate_threshold: float = Field(default=0.25, ge=0.1, le=0.5)
    intermediate_to_wet_threshold: float = Field(default=0.55, ge=0.4, le=0.8)
    wet_to_intermediate_threshold: float = Field(default=0.4, ge=0.2, le=0.6)
    intermediate_to_slick_threshold: float = Field(default=0.15, ge=0.05, le=0.3)

    # Temperature thresholds
    slick_optimal_temp: float = Field(default=85.0, ge=70, le=110)
    intermediate_optimal_temp: float = Field(default=60.0, ge=50, le=80)
    wet_optimal_temp: float = Field(default=50.0, ge=40, le=70)

    # Performance parameters
    intermediate_vs_slick_dry_delta: float = Field(default=2.5, ge=1.0, le=5.0)  # sec/lap slower on dry  # noqa: E501
    wet_vs_intermediate_damp_delta: float = Field(default=1.5, ge=0.5, le=3.0)  # sec/lap slower on damp  # noqa: E501
    slick_vs_intermediate_wet_delta: float = Field(default=4.0, ge=2.0, le=8.0)  # sec/lap slower on wet  # noqa: E501

    # Hysteresis to prevent flapping
    hysteresis: float = Field(default=0.05, ge=0.01, le=0.2)

    model_config = {"use_enum_values": True}

    def assess_crossover(
        self,
        current_compound: str,
        track_wetness: float,
        track_temp: float,
        racing_line_wetness: float,
        off_line_wetness: float,
        tyre_temp: float,
        tyre_wear: float,
        forecast_wetness: float | None = None,
    ) -> TyreCrossoverAssessment:
        """Assess whether a compound change is recommended."""

        # Determine current track state
        effective_wetness = (racing_line_wetness + off_line_wetness) / 2

        # Current compound category
        is_slick = current_compound in ("soft", "medium", "hard")
        is_intermediate = current_compound == "intermediate"
        is_wet = current_compound == "wet"

        # Assess based on wetness
        if is_slick:
            if effective_wetness > self.slick_to_intermediate_threshold:
                # Conditions favor intermediate
                confidence = min(1.0, (effective_wetness - self.slick_to_intermediate_threshold) / 0.2)  # noqa: E501
                return TyreCrossoverAssessment(
                    recommended_compound="intermediate",
                    confidence=confidence,
                    expected_delta=-1.5,  # Faster on wet
                    reason=f"Track wetness ({effective_wetness:.2f}) exceeds slick threshold",
                    crossover_lap=None,
                )
            elif effective_wetness > self.wet_to_intermediate_threshold:
                # Borderline - consider intermediate
                confidence = min(1.0, (effective_wetness - self.wet_to_intermediate_threshold) / 0.1)  # noqa: E501
                return TyreCrossoverAssessment(
                    recommended_compound="intermediate",
                    confidence=confidence * 0.5,
                    expected_delta=-0.5,
                    reason=f"Track wetness ({effective_wetness:.2f}) approaching intermediate window",  # noqa: E501
                )

        elif is_intermediate:
            # Check for wet
            if effective_wetness > self.intermediate_to_wet_threshold:
                confidence = min(1.0, (effective_wetness - self.intermediate_to_wet_threshold) / 0.15)  # noqa: E501
                return TyreCrossoverAssessment(
                    recommended_compound="wet",
                    confidence=confidence,
                    expected_delta=-2.0,
                    reason=f"Track wetness ({effective_wetness:.2f}) exceeds intermediate threshold",  # noqa: E501
                )
            # Check for slick
            elif effective_wetness < self.intermediate_to_slick_threshold + self.hysteresis:
                confidence = min(1.0, (self.intermediate_to_slick_threshold + self.hysteresis - effective_wetness) / 0.1)  # noqa: E501
                return TyreCrossoverAssessment(
                    recommended_compound="medium",  # Default slick
                    confidence=confidence,
                    expected_delta=-2.5,
                    reason=f"Track drying ({effective_wetness:.2f}) favors slicks",
                )

        elif is_wet:
            if effective_wetness < self.wet_to_intermediate_threshold - self.hysteresis:
                confidence = min(1.0, (self.wet_to_intermediate_threshold - self.hysteresis - effective_wetness) / 0.1)  # noqa: E501
                return TyreCrossoverAssessment(
                    recommended_compound="intermediate",
                    confidence=confidence,
                    expected_delta=-1.5,
                    reason=f"Track drying ({effective_wetness:.2f}) favors intermediate",
                )

        # No crossover recommended
        return TyreCrossoverAssessment(
            recommended_compound=current_compound,
            confidence=0.0,
            expected_delta=0.0,
            reason="Current compound optimal for conditions",
        )


class ForecastUncertainty(BaseModel):
    """Weather forecast with uncertainty."""

    # Per-lap forecasts with confidence
    lap_forecasts: list[dict[str, Any]] = Field(default_factory=list)

    # Summary
    rain_probability: float = Field(default=0.1, ge=0, le=1)
    max_precipitation: float = Field(default=0.0, ge=0)
    temperature_range: tuple[float, float] = (20.0, 30.0)

    # Uncertainty parameters
    forecast_error_sigma: float = Field(default=0.15, ge=0.05, le=0.5)
    confidence_decay_per_lap: float = Field(default=0.05, ge=0.01, le=0.2)

    model_config = {"use_enum_values": True}

    def get_forecast_for_lap(self, lap: int) -> dict[str, Any]:
        """Get forecast for a specific lap with uncertainty."""
        if lap < len(self.lap_forecasts):
            base = self.lap_forecasts[lap].copy()
            # Add uncertainty based on horizon
            confidence = max(0.1, 1.0 - lap * self.confidence_decay_per_lap)
            base["confidence"] = confidence
            return base

        # Extrapolate last known
        return self.lap_forecasts[-1].copy() if self.lap_forecasts else {}

    def get_rain_probability_at_lap(self, lap: int) -> float:
        """Get rain probability at a specific lap."""
        forecast = self.get_forecast_for_lap(lap)
        return 1.0 if float(forecast.get("precipitation_rate", 0)) > 0 else 0.0


class OvertakeZone(BaseModel):
    """Track-specific overtaking zone definition."""

    sector: int
    name: str = ""

    # Zone characteristics
    entry_speed_kmh: float = Field(default=250.0, ge=100, le=350)
    braking_intensity: float = Field(default=0.5, ge=0, le=1)  # 0 = light, 1 = heavy
    straight_length_km: float = Field(default=0.5, ge=0.1, le=2.0)
    drs_available: bool = False
    drs_zone_length_km: float = Field(default=0.0, ge=0)

    # Difficulty metrics
    overtake_difficulty: float = Field(default=50.0, ge=0, le=100)
    defense_difficulty: float = Field(default=50.0, ge=0, le=100)

    # Corner characteristics
    corner_type: str = "medium"  # hairpin, slow, medium, fast, high_speed, chicane
    corner_angle: float = 90.0  # degrees
    entry_width: float = 12.0  # meters
    exit_width: float = 12.0  # meters

    # Performance factors
    straight_line_importance: float = Field(default=0.5, ge=0, le=1)
    braking_importance: float = Field(default=0.5, ge=0, le=1)
    traction_importance: float = Field(default=0.5, ge=0, le=1)

    model_config = {"use_enum_values": True}

    def get_overtake_difficulty_for_car(
        self,
        car_straight_line_perf: float,
        car_braking_perf: float,
        car_traction_perf: float,
    ) -> float:
        """Get effective overtake difficulty for a specific car."""
        base = self.overtake_difficulty

        # Adjust for car strengths
        straight_adj = (75 - car_straight_line_perf) * self.straight_line_importance * 0.2
        braking_adj = (75 - car_braking_perf) * self.braking_importance * 0.2
        traction_adj = (75 - car_traction_perf) * self.traction_importance * 0.15

        return max(0, min(100, base + straight_adj + braking_adj + traction_adj))

    def get_defense_difficulty_for_car(
        self,
        car_straight_line_perf: float,
        car_braking_perf: float,
        car_traction_perf: float,
    ) -> float:
        """Get effective defense difficulty for a specific car."""
        base = self.defense_difficulty

        # Defender benefits from car strengths differently
        straight_adj = (75 - car_straight_line_perf) * self.straight_line_importance * 0.15
        braking_adj = (75 - car_braking_perf) * self.braking_importance * 0.25
        traction_adj = (75 - car_traction_perf) * self.traction_importance * 0.1

        return max(0, min(100, base + straight_adj + braking_adj + traction_adj))


class TrackOvertakeMap(BaseModel):
    """Collection of overtake zones for a track."""

    track_id: str
    zones: list[OvertakeZone] = Field(default_factory=list)

    model_config = {"use_enum_values": True}

    def get_zone_for_sector(self, sector: int) -> OvertakeZone | None:
        """Get overtake zone for a sector."""
        for zone in self.zones:
            if zone.sector == sector:
                return zone
        return None

    def get_best_overtake_zone(
        self,
        car_straight_line_perf: float,
        car_braking_perf: float,
        car_traction_perf: float,
    ) -> OvertakeZone | None:
        """Get the best overtake zone for a car."""
        if not self.zones:
            return None

        best_zone = None
        best_score = float('inf')

        for zone in self.zones:
            difficulty = zone.get_overtake_difficulty_for_car(
                car_straight_line_perf, car_braking_perf, car_traction_perf
            )
            if difficulty < best_score:
                best_score = difficulty
                best_zone = zone

        return best_zone


def create_bahrain_overtake_map() -> TrackOvertakeMap:
    """Create overtake map for Bahrain."""
    return TrackOvertakeMap(
        track_id="bahrain",
        zones=[
            OvertakeZone(
                sector=0,
                name="Turn 1-4 Complex",
                entry_speed_kmh=310,
                braking_intensity=0.8,
                straight_length_km=0.8,
                drs_available=True,
                drs_zone_length_km=0.6,
                overtake_difficulty=30,
                defense_difficulty=35,
                corner_type="slow",
                straight_line_importance=0.7,
                braking_importance=0.8,
                traction_importance=0.6,
            ),
            OvertakeZone(
                sector=1,
                name="Turn 8-10 Complex",
                entry_speed_kmh=280,
                braking_intensity=0.6,
                straight_length_km=0.4,
                drs_available=False,
                overtake_difficulty=40,
                defense_difficulty=45,
                corner_type="medium",
                straight_line_importance=0.4,
                braking_importance=0.6,
                traction_importance=0.5,
            ),
            OvertakeZone(
                sector=2,
                name="Turn 11-15 (DRS Zone)",
                entry_speed_kmh=320,
                braking_intensity=0.85,
                straight_length_km=1.1,
                drs_available=True,
                drs_zone_length_km=0.6,
                overtake_difficulty=25,
                defense_difficulty=30,
                corner_type="slow",
                straight_line_importance=0.8,
                braking_importance=0.9,
                traction_importance=0.5,
            ),
        ]
    )


def create_monaco_overtake_map() -> TrackOvertakeMap:
    """Create overtake map for Monaco."""
    return TrackOvertakeMap(
        track_id="monaco",
        zones=[
            OvertakeZone(
                sector=0,
                name="Ste Devote - Casino",
                entry_speed_kmh=220,
                braking_intensity=0.9,
                straight_length_km=0.1,
                drs_available=False,
                overtake_difficulty=95,
                defense_difficulty=95,
                corner_type="hairpin",
                straight_line_importance=0.1,
                braking_importance=0.9,
                traction_importance=0.8,
            ),
            OvertakeZone(
                sector=1,
                name="Tunnel - Chicane",
                entry_speed_kmh=280,
                braking_intensity=0.85,
                straight_length_km=0.3,
                drs_available=False,
                overtake_difficulty=95,
                defense_difficulty=95,
                corner_type="chicane",
                straight_line_importance=0.2,
                braking_importance=0.85,
                traction_importance=0.7,
            ),
            OvertakeZone(
                sector=2,
                name="Tabac - Swimming Pool - La Rascasse",
                entry_speed_kmh=200,
                braking_intensity=0.7,
                straight_length_km=0.2,
                drs_available=False,
                overtake_difficulty=95,
                defense_difficulty=95,
                corner_type="slow",
                straight_line_importance=0.1,
                braking_importance=0.8,
                traction_importance=0.7,
            ),
        ]
    )


def create_monza_overtake_map() -> TrackOvertakeMap:
    """Create overtake map for Monza."""
    return TrackOvertakeMap(
        track_id="monza",
        zones=[
            OvertakeZone(
                sector=0,
                name="Rettifilo - Turn 1-2 (DRS)",
                entry_speed_kmh=340,
                braking_intensity=0.95,
                straight_length_km=1.2,
                drs_available=True,
                drs_zone_length_km=0.8,
                overtake_difficulty=20,
                defense_difficulty=25,
                corner_type="slow",
                straight_line_importance=0.9,
                braking_importance=0.95,
                traction_importance=0.4,
            ),
            OvertakeZone(
                sector=1,
                name="Curva Grande - Lesmos (DRS)",
                entry_speed_kmh=330,
                braking_intensity=0.7,
                straight_length_km=0.8,
                drs_available=True,
                drs_zone_length_km=0.5,
                overtake_difficulty=25,
                defense_difficulty=30,
                corner_type="fast",
                straight_line_importance=0.7,
                braking_importance=0.6,
                traction_importance=0.5,
            ),
            OvertakeZone(
                sector=2,
                name="Ascari - Parabolica",
                entry_speed_kmh=310,
                braking_intensity=0.6,
                straight_length_km=0.3,
                drs_available=False,
                overtake_difficulty=30,
                defense_difficulty=35,
                corner_type="fast",
                straight_line_importance=0.4,
                braking_importance=0.5,
                traction_importance=0.6,
            ),
        ]
    )


def get_overtake_map_for_track(track_id: str) -> TrackOvertakeMap | None:
    """Get overtake map for a track by ID."""
    maps = {
        "bahrain": create_bahrain_overtake_map(),
        "monaco": create_monaco_overtake_map(),
        "monza": create_monza_overtake_map(),
    }
    return maps.get(track_id)
