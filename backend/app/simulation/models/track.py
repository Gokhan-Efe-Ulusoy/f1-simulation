from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TrackType(str, Enum):
    """Track categorization."""

    STREET = "street"
    PERMANENT = "permanent"
    HYBRID = "hybrid"


class CornerType(str, Enum):
    """Corner categorization."""

    HAIRPIN = "hairpin"          # < 80 km/h, ~180 deg
    SLOW = "slow"                # 80-130 km/h, 90-150 deg
    MEDIUM = "medium"            # 130-200 km/h, 45-120 deg
    FAST = "fast"                # 200-250 km/h, 30-90 deg
    HIGH_SPEED = "high_speed"    # > 250 km/h, < 45 deg
    CHICANE = "chicane"          # S-bend, quick direction change
    DOUBLE_APEX = "double_apex"  # Two apexes in one corner


class Track(BaseModel):
    """Formula 1 Circuit model with statistical characteristics.
    
    For initial implementation, tracks are represented by statistical
    characteristics rather than a full physical circuit model.
    """

    # Identity
    id: str
    name: str
    country: str
    city: str
    track_type: TrackType = TrackType.PERMANENT

    # Layout
    length_km: float = Field(gt=0, default=5.0)
    number_of_laps: int = Field(gt=0, default=70)
    race_distance_km: float = Field(gt=0, default=305.0)
    number_of_corners: int = Field(gt=0, default=15)
    number_of_sectors: int = Field(default=3, ge=2, le=4)
    sector_lengths_km: list[float] = Field(default_factory=list)  # Must sum to length_km

    # Corner breakdown
    corner_distribution: dict[CornerType, int] = Field(default_factory=lambda: {
        CornerType.HAIRPIN: 2,
        CornerType.SLOW: 3,
        CornerType.MEDIUM: 5,
        CornerType.FAST: 3,
        CornerType.HIGH_SPEED: 1,
        CornerType.CHICANE: 1,
        CornerType.DOUBLE_APEX: 0,
    })

    # Straights
    longest_straight_km: float = Field(default=1.2, ge=0.2, le=2.5)
    total_straight_length_km: float = Field(default=2.5, ge=0.5)
    drs_zones: int = Field(default=2, ge=0, le=4)
    drs_zone_lengths_km: list[float] = Field(default_factory=list)

    # Track characteristics (0-100)
    overtaking_difficulty: float = Field(ge=0, le=100, default=50)
    # Higher = harder to overtake (Monaco ~95, Bahrain ~30)

    # Sector characteristics
    sector_corner_counts: dict[int, dict[CornerType, int]] = Field(default_factory=dict)
    sector_straight_lengths_km: list[float] = Field(default_factory=list)
    sector_drs_zones: list[int] = Field(default_factory=list)
    sector_overtaking_difficulty: list[float] = Field(default_factory=list)
    sector_dirty_air_sensitivity: list[float] = Field(default_factory=list)
    sector_braking_difficulty: list[float] = Field(default_factory=list)
    sector_traction_demand: list[float] = Field(default_factory=list)
    sector_aero_dependency: list[float] = Field(default_factory=list)
    sector_overtaking_opportunity: list[float] = Field(default_factory=list)
    sector_defense_difficulty: list[float] = Field(default_factory=list)

    # Tyre stress
    front_tyre_stress: float = Field(ge=0, le=100, default=50)
    rear_tyre_stress: float = Field(ge=0, le=100, default=50)
    lateral_energy: float = Field(ge=0, le=100, default=50)   # Lateral load
    traction_energy: float = Field(ge=0, le=100, default=50)  # Traction zones
    braking_energy: float = Field(ge=0, le=100, default=50)   # Braking zones

    # Degradation profile
    degradation_profile: str = "linear"  # "linear", "exponential", "cliff", "low"
    base_degradation_rate: float = Field(default=0.05, ge=0.01, le=0.20)  # sec/lap base
    degradation_exponent: float = Field(default=1.2, ge=1.0, le=2.0)  # For exponential

    # Aero sensitivity
    aero_sensitivity: float = Field(ge=0, le=100, default=50)
    # How much lap time improves per point of downforce
    downforce_sensitivity: float = Field(default=0.03, ge=0.01, le=0.10)  # sec per downforce point
    drag_sensitivity: float = Field(default=0.02, ge=0.005, le=0.05)  # sec per drag point

    # Track evolution
    track_evolution_rate: float = Field(default=0.02, ge=0.005, le=0.08)  # sec/lap improvement
    track_evolution_saturation: float = Field(default=1.5, ge=0.5, le=3.0)  # Max improvement
    rubber_in_rate: float = Field(default=0.1, ge=0.02, le=0.3)  # How fast track rubbers in
    green_track_penalty: float = Field(default=1.5, ge=0.5, le=3.0)  # Sec on green track

    # Environmental
    base_ambient_temp: float = Field(default=25.0, ge=5, le=45)
    base_track_temp: float = Field(default=35.0, ge=10, le=60)
    humidity: float = Field(default=60.0, ge=0, le=100)
    altitude_m: float = Field(default=0, ge=0, le=3000)

    # Weather
    rain_probability: float = Field(default=0.1, ge=0, le=1)
    safety_car_probability: float = Field(default=0.15, ge=0, le=1)
    vsc_probability: float = Field(default=0.10, ge=0, le=1)

    # Braking
    number_of_braking_zones: int = Field(default=8, ge=3, le=15)
    heavy_braking_zones: int = Field(default=4, ge=1, le=8)
    # Heavy braking = >1.5G deceleration from >300km/h

    # Lap time reference
    reference_lap_time: float = Field(default=90.0, ge=60, le=120)  # Base lap time in seconds
    pole_lap_time: float = Field(default=88.0, ge=60, le=120)
    race_lap_record: float = Field(default=89.0, ge=60, le=120)

    # Pit lane
    pit_lane_length_km: float = Field(default=0.4, ge=0.2, le=0.8)
    pit_lane_speed_limit_kmh: float = Field(default=80, ge=60, le=100)
    pit_stop_time_loss: float = Field(default=22.0, ge=15, le=30)  # Total time loss vs racing

    # History
    first_gp_year: int = 1950
    most_recent_gp_year: int = 2024
    total_races_held: int = 50

    # Metadata
    is_sprint_eligible: bool = True
    lap_record_holder: str | None = None
    lap_record_year: int | None = None

    model_config = {"use_enum_values": True}

    def get_corner_count(self) -> int:
        return sum(self.corner_distribution.values())

    def get_corner_type_ratio(self, corner_type: CornerType) -> float:
        total = self.get_corner_count()
        if total == 0:
            return 0.0
        return self.corner_distribution.get(corner_type, 0) / total

    def get_overtaking_difficulty_normalized(self) -> float:
        """Return 0-1 where 0 = easy overtaking, 1 = very difficult."""
        return self.overtaking_difficulty / 100

    def get_tyre_degradation_per_lap(self, compound: str, car_tyre_wear: float = 1.0) -> float:
        """Get base degradation per lap for a compound.
        
        car_tyre_wear: Car's tyre wear characteristic multiplier (1.0 = average)
        """
        compound_multipliers = {
            "soft": 1.5,
            "medium": 1.0,
            "hard": 0.7,
            "intermediate": 1.2,
            "wet": 1.0,
        }
        mult = compound_multipliers.get(compound, 1.0)

        # Average tyre stress
        avg_stress = (self.front_tyre_stress + self.rear_tyre_stress) / 2
        stress_factor = 0.5 + (avg_stress / 100) * 1.0  # 0.5 to 1.5

        return self.base_degradation_rate * mult * stress_factor * car_tyre_wear

    def get_fuel_sensitivity(self) -> float:
        """Get fuel sensitivity (sec per 10kg)."""
        # Heavier tracks = more acceleration zones = higher fuel sensitivity
        # Based on number of slow corners + hairpins
        accel_zones = (
            self.corner_distribution.get(CornerType.HAIRPIN, 0) +
            self.corner_distribution.get(CornerType.SLOW, 0) +
            self.corner_distribution.get(CornerType.CHICANE, 0)
        )
        return 0.025 + accel_zones * 0.002  # 0.025 to ~0.055

    def get_drs_effectiveness(self) -> float:
        """Get DRS effectiveness in seconds."""
        # Based on DRS zone length and straight line speed
        total_drs = sum(self.drs_zone_lengths_km) if self.drs_zone_lengths_km else self.drs_zones * 0.5  # noqa: E501
        return min(0.5, total_drs * 0.15)  # Max ~0.5s

    def get_track_evolution_per_lap(self, cars_on_track: int = 20) -> float:
        """Get track evolution per lap in seconds."""
        # More cars = faster rubber in
        car_factor = min(1.5, cars_on_track / 20)
        return self.track_evolution_rate * car_factor

    def get_base_lap_time(self, car_performance: float = 75, driver_skill: float = 75) -> float:
        """Estimate base lap time for given car/driver performance.
        
        car_performance: 0-100
        driver_skill: 0-100
        """
        # Reference is roughly for 75/75
        perf_delta = (75 - car_performance) * 0.15  # ~0.15s per point
        driver_delta = (75 - driver_skill) * 0.10   # ~0.10s per point
        return self.reference_lap_time + perf_delta + driver_delta

    def get_sector_times(self, lap_time: float) -> list[float]:
        """Split lap time into sectors based on sector lengths."""
        if not self.sector_lengths_km or len(self.sector_lengths_km) != self.number_of_sectors:
            return [lap_time / self.number_of_sectors] * self.number_of_sectors

        total = sum(self.sector_lengths_km)
        return [lap_time * (l / total) for l in self.sector_lengths_km]

    def get_track_type_category(self) -> str:
        """Categorize track for car setup purposes."""
        hd_ratio = self.get_corner_type_ratio(CornerType.HIGH_SPEED) + self.get_corner_type_ratio(CornerType.FAST)  # noqa: E501
        ld_ratio = self.get_corner_type_ratio(CornerType.SLOW) + self.get_corner_type_ratio(CornerType.HAIRPIN)  # noqa: E501

        if hd_ratio > 0.4:
            return "high_downforce"
        elif ld_ratio > 0.4:
            return "low_downforce"
        elif self.track_type == TrackType.STREET:
            return "street"
        else:
            return "balanced"

    def get_pit_lane_time_total(self) -> float:
        """Get total pit lane time loss including stationary stop."""
        pit_lane_time = (self.pit_lane_length_km / (self.pit_lane_speed_limit_kmh / 3600)) - \
                        (self.pit_lane_length_km / (300 / 3.6))  # vs racing at 300km/h
        return pit_lane_time + 2.5  # Add stationary stop time

    def get_sector_corner_counts(self, sector: int) -> dict[CornerType, int]:
        """Get corner counts for a specific sector (0-indexed)."""
        if sector < 0 or sector >= self.number_of_sectors:
            return {}
        return self.sector_corner_counts.get(sector, {})

    def get_sector_straight_length(self, sector: int) -> float:
        """Get straight length for a specific sector in km."""
        if sector < 0 or sector >= len(self.sector_straight_lengths_km):
            return 0.0
        return self.sector_straight_lengths_km[sector]

    def get_sector_drs_zones(self, sector: int) -> int:
        """Get number of DRS zones in a specific sector."""
        if sector < 0 or sector >= len(self.sector_drs_zones):
            return 0
        return self.sector_drs_zones[sector]

    def get_sector_overtaking_difficulty(self, sector: int) -> float:
        """Get overtaking difficulty for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_overtaking_difficulty):
            return self.overtaking_difficulty
        return self.sector_overtaking_difficulty[sector]

    def get_sector_dirty_air_sensitivity(self, sector: int) -> float:
        """Get dirty air sensitivity for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_dirty_air_sensitivity):
            return 50.0
        return self.sector_dirty_air_sensitivity[sector]

    def get_sector_braking_difficulty(self, sector: int) -> float:
        """Get braking difficulty for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_braking_difficulty):
            return 50.0
        return self.sector_braking_difficulty[sector]

    def get_sector_traction_demand(self, sector: int) -> float:
        """Get traction demand for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_traction_demand):
            return 50.0
        return self.sector_traction_demand[sector]

    def get_sector_aero_dependency(self, sector: int) -> float:
        """Get aero dependency for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_aero_dependency):
            return 50.0
        return self.sector_aero_dependency[sector]

    def get_sector_overtaking_opportunity(self, sector: int) -> float:
        """Get overtaking opportunity for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_overtaking_opportunity):
            return 50.0
        return self.sector_overtaking_opportunity[sector]

    def get_sector_defense_difficulty(self, sector: int) -> float:
        """Get defense difficulty for a specific sector (0-100)."""
        if sector < 0 or sector >= len(self.sector_defense_difficulty):
            return 50.0
        return self.sector_defense_difficulty[sector]

    def get_sector_corner_type_ratio(self, sector: int, corner_type: CornerType) -> float:
        """Get ratio of a specific corner type in a sector."""
        counts = self.get_sector_corner_counts(sector)
        total = sum(counts.values())
        if total == 0:
            return 0.0
        return counts.get(corner_type, 0) / total

    def initialize_sector_characteristics(self) -> None:
        """Initialize sector characteristics from global track data if not set."""
        n = self.number_of_sectors

        # Initialize sector corner counts if empty
        if not self.sector_corner_counts:
            # Distribute corners evenly across sectors
            for corner_type, count in self.corner_distribution.items():
                per_sector = count // n
                remainder = count % n
                for s in range(n):
                    cnt = per_sector + (1 if s < remainder else 0)
                    if cnt > 0:
                        if s not in self.sector_corner_counts:
                            self.sector_corner_counts[s] = {}
                        self.sector_corner_counts[s][corner_type] = cnt

        # Initialize straight lengths if empty
        if not self.sector_straight_lengths_km:
            total_straight = self.total_straight_length_km
            per_sector = total_straight / n
            self.sector_straight_lengths_km = [per_sector] * n

        # Initialize DRS zones if empty
        if not self.sector_drs_zones:
            per_sector_int = self.drs_zones // n
            remainder = self.drs_zones % n
            self.sector_drs_zones = [per_sector_int + (1 if s < remainder else 0) for s in range(n)]

        # Initialize sector overtaking difficulty if empty
        if not self.sector_overtaking_difficulty:
            # Base on overall difficulty with some variation
            base = self.overtaking_difficulty
            self.sector_overtaking_difficulty = [base + (s - n/2) * 2 for s in range(n)]

        # Initialize dirty air sensitivity if empty
        if not self.sector_dirty_air_sensitivity:
            base = self.aero_sensitivity
            self.sector_dirty_air_sensitivity = [base + (s - n/2) * 3 for s in range(n)]

        # Initialize braking difficulty if empty
        if not self.sector_braking_difficulty:
            base = self.braking_energy
            self.sector_braking_difficulty = [base] * n

        # Initialize traction demand if empty
        if not self.sector_traction_demand:
            base = self.traction_energy
            self.sector_traction_demand = [base] * n

        # Initialize aero dependency if empty
        if not self.sector_aero_dependency:
            base = self.aero_sensitivity
            self.sector_aero_dependency = [base] * n

        # Initialize overtaking opportunity if empty
        if not self.sector_overtaking_opportunity:
            base = 100 - self.overtaking_difficulty
            self.sector_overtaking_opportunity = [base + (s - n/2) * 2 for s in range(n)]

        # Initialize defense difficulty if empty
        if not self.sector_defense_difficulty:
            base = self.overtaking_difficulty
            self.sector_defense_difficulty = [base + (s - n/2) * 2 for s in range(n)]


# Pre-defined F1 2024 tracks
def get_2024_calendar() -> list[Track]:
    """Get the 2024 F1 calendar tracks."""
    return [
        Track(
            id="bahrain",
            name="Bahrain International Circuit",
            country="Bahrain",
            city="Sakhir",
            track_type=TrackType.PERMANENT,
            length_km=5.412,
            number_of_laps=57,
            race_distance_km=308.238,
            number_of_corners=15,
            corner_distribution={
                CornerType.HAIRPIN: 2,
                CornerType.SLOW: 3,
                CornerType.MEDIUM: 4,
                CornerType.FAST: 3,
                CornerType.HIGH_SPEED: 2,
                CornerType.CHICANE: 1,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.HAIRPIN: 1, CornerType.SLOW: 1, CornerType.MEDIUM: 1, CornerType.FAST: 1},  # noqa: E501
                1: {CornerType.HAIRPIN: 0, CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 1, CornerType.CHICANE: 1},  # noqa: E501
                2: {CornerType.HAIRPIN: 1, CornerType.SLOW: 1, CornerType.MEDIUM: 1, CornerType.FAST: 1, CornerType.HIGH_SPEED: 2},  # noqa: E501
            },
            sector_straight_lengths_km=[0.6, 0.4, 0.5],
            sector_drs_zones=[1, 0, 1],
            sector_overtaking_difficulty=[30, 40, 35],
            sector_dirty_air_sensitivity=[35, 45, 40],
            sector_braking_difficulty=[75, 65, 70],
            sector_traction_demand=[65, 55, 60],
            sector_aero_dependency=[35, 45, 40],
            sector_overtaking_opportunity=[70, 55, 65],
            sector_defense_difficulty=[30, 45, 40],
            longest_straight_km=1.1,
            overtaking_difficulty=35,
            front_tyre_stress=60,
            rear_tyre_stress=55,
            lateral_energy=65,
            traction_energy=60,
            braking_energy=70,
            degradation_profile="linear",
            base_degradation_rate=0.045,
            aero_sensitivity=40,
            track_evolution_rate=0.025,
            safety_car_probability=0.20,
            reference_lap_time=90.5,
            pit_stop_time_loss=20.5,
        ),
        Track(
            id="saudi_arabia",
            name="Jeddah Corniche Circuit",
            country="Saudi Arabia",
            city="Jeddah",
            track_type=TrackType.STREET,
            length_km=6.174,
            number_of_laps=50,
            race_distance_km=308.45,
            number_of_corners=27,
            corner_distribution={
                CornerType.HAIRPIN: 0,
                CornerType.SLOW: 2,
                CornerType.MEDIUM: 8,
                CornerType.FAST: 12,
                CornerType.HIGH_SPEED: 4,
                CornerType.CHICANE: 1,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 4, CornerType.HIGH_SPEED: 1},  # noqa: E501
                1: {CornerType.SLOW: 0, CornerType.MEDIUM: 3, CornerType.FAST: 4, CornerType.HIGH_SPEED: 2},  # noqa: E501
                2: {CornerType.SLOW: 1, CornerType.MEDIUM: 3, CornerType.FAST: 4, CornerType.HIGH_SPEED: 1, CornerType.CHICANE: 1},  # noqa: E501
            },
            sector_straight_lengths_km=[0.5, 0.8, 0.4],
            sector_drs_zones=[1, 2, 0],
            sector_overtaking_difficulty=[35, 45, 40],
            sector_dirty_air_sensitivity=[55, 65, 60],
            sector_braking_difficulty=[45, 55, 50],
            sector_traction_demand=[35, 45, 40],
            sector_aero_dependency=[55, 65, 60],
            sector_overtaking_opportunity=[65, 55, 60],
            sector_defense_difficulty=[35, 45, 40],
            longest_straight_km=1.0,
            overtaking_difficulty=40,
            front_tyre_stress=70,
            rear_tyre_stress=65,
            lateral_energy=85,
            traction_energy=40,
            braking_energy=50,
            degradation_profile="low",
            base_degradation_rate=0.035,
            aero_sensitivity=60,
            track_evolution_rate=0.030,
            safety_car_probability=0.45,
            reference_lap_time=89.8,
            pit_stop_time_loss=21.0,
        ),
        Track(
            id="australia",
            name="Albert Park Circuit",
            country="Australia",
            city="Melbourne",
            track_type=TrackType.STREET,
            length_km=5.278,
            number_of_laps=58,
            race_distance_km=306.124,
            number_of_corners=14,
            corner_distribution={
                CornerType.HAIRPIN: 1,
                CornerType.SLOW: 3,
                CornerType.MEDIUM: 5,
                CornerType.FAST: 3,
                CornerType.HIGH_SPEED: 1,
                CornerType.CHICANE: 1,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.HAIRPIN: 1, CornerType.SLOW: 1, CornerType.MEDIUM: 1, CornerType.FAST: 1},  # noqa: E501
                1: {CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 1, CornerType.CHICANE: 1},  # noqa: E501
                2: {CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 1, CornerType.HIGH_SPEED: 1},  # noqa: E501
            },
            sector_straight_lengths_km=[0.5, 0.3, 0.4],
            sector_drs_zones=[1, 0, 1],
            sector_overtaking_difficulty=[45, 55, 50],
            sector_dirty_air_sensitivity=[45, 55, 50],
            sector_braking_difficulty=[60, 65, 55],
            sector_traction_demand=[55, 55, 55],
            sector_aero_dependency=[45, 55, 50],
            sector_overtaking_opportunity=[55, 45, 50],
            sector_defense_difficulty=[45, 55, 50],
            longest_straight_km=0.9,
            overtaking_difficulty=50,
            front_tyre_stress=55,
            rear_tyre_stress=55,
            lateral_energy=60,
            traction_energy=55,
            braking_energy=60,
            degradation_profile="linear",
            base_degradation_rate=0.040,
            aero_sensitivity=50,
            track_evolution_rate=0.020,
            safety_car_probability=0.25,
            reference_lap_time=81.0,
            pit_stop_time_loss=22.5,
        ),
        Track(
            id="monaco",
            name="Circuit de Monaco",
            country="Monaco",
            city="Monte Carlo",
            track_type=TrackType.STREET,
            length_km=3.337,
            number_of_laps=78,
            race_distance_km=260.286,
            number_of_corners=19,
            corner_distribution={
                CornerType.HAIRPIN: 3,
                CornerType.SLOW: 8,
                CornerType.MEDIUM: 5,
                CornerType.FAST: 2,
                CornerType.HIGH_SPEED: 0,
                CornerType.CHICANE: 1,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.HAIRPIN: 1, CornerType.SLOW: 3, CornerType.MEDIUM: 2},
                1: {CornerType.HAIRPIN: 1, CornerType.SLOW: 3, CornerType.MEDIUM: 2, CornerType.CHICANE: 1},  # noqa: E501
                2: {CornerType.HAIRPIN: 1, CornerType.SLOW: 2, CornerType.MEDIUM: 1, CornerType.FAST: 2},  # noqa: E501
            },
            sector_straight_lengths_km=[0.1, 0.2, 0.2],
            sector_drs_zones=[0, 0, 0],
            sector_overtaking_difficulty=[95, 95, 95],
            sector_dirty_air_sensitivity=[75, 70, 65],
            sector_braking_difficulty=[45, 40, 35],
            sector_traction_demand=[75, 70, 65],
            sector_aero_dependency=[75, 70, 65],
            sector_overtaking_opportunity=[5, 5, 5],
            sector_defense_difficulty=[95, 95, 95],
            longest_straight_km=0.5,
            overtaking_difficulty=95,
            front_tyre_stress=40,
            rear_tyre_stress=45,
            lateral_energy=50,
            traction_energy=70,
            braking_energy=40,
            degradation_profile="low",
            base_degradation_rate=0.020,
            aero_sensitivity=70,
            track_evolution_rate=0.035,
            green_track_penalty=2.5,
            safety_car_probability=0.55,
            reference_lap_time=73.5,
            pit_stop_time_loss=19.0,
        ),
        Track(
            id="spain",
            name="Circuit de Barcelona-Catalunya",
            country="Spain",
            city="Montmeló",
            track_type=TrackType.PERMANENT,
            length_km=4.675,
            number_of_laps=66,
            race_distance_km=308.424,
            number_of_corners=16,
            corner_distribution={
                CornerType.HAIRPIN: 1,
                CornerType.SLOW: 3,
                CornerType.MEDIUM: 6,
                CornerType.FAST: 4,
                CornerType.HIGH_SPEED: 1,
                CornerType.CHICANE: 1,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.HAIRPIN: 1, CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 1},  # noqa: E501
                1: {CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 2, CornerType.CHICANE: 1},  # noqa: E501
                2: {CornerType.SLOW: 1, CornerType.MEDIUM: 2, CornerType.FAST: 1, CornerType.HIGH_SPEED: 1},  # noqa: E501
            },
            sector_straight_lengths_km=[0.4, 0.3, 0.3],
            sector_drs_zones=[0, 1, 0],
            sector_overtaking_difficulty=[45, 40, 50],
            sector_dirty_air_sensitivity=[50, 60, 55],
            sector_braking_difficulty=[50, 60, 55],
            sector_traction_demand=[60, 70, 65],
            sector_aero_dependency=[50, 60, 55],
            sector_overtaking_opportunity=[55, 60, 50],
            sector_defense_difficulty=[45, 40, 50],
            longest_straight_km=1.0,
            overtaking_difficulty=45,
            front_tyre_stress=75,
            rear_tyre_stress=70,
            lateral_energy=75,
            traction_energy=65,
            braking_energy=55,
            degradation_profile="exponential",
            base_degradation_rate=0.055,
            degradation_exponent=1.3,
            aero_sensitivity=55,
            track_evolution_rate=0.015,
            safety_car_probability=0.10,
            reference_lap_time=77.0,
            pit_stop_time_loss=23.0,
        ),
        Track(
            id="monza",
            name="Autodromo Nazionale Monza",
            country="Italy",
            city="Monza",
            track_type=TrackType.PERMANENT,
            length_km=5.793,
            number_of_laps=53,
            race_distance_km=306.720,
            number_of_corners=11,
            corner_distribution={
                CornerType.HAIRPIN: 0,
                CornerType.SLOW: 2,
                CornerType.MEDIUM: 2,
                CornerType.FAST: 3,
                CornerType.HIGH_SPEED: 4,
                CornerType.CHICANE: 0,
                CornerType.DOUBLE_APEX: 0,
            },
            sector_corner_counts={
                0: {CornerType.SLOW: 1, CornerType.FAST: 1, CornerType.HIGH_SPEED: 1},
                1: {CornerType.SLOW: 0, CornerType.MEDIUM: 1, CornerType.FAST: 1, CornerType.HIGH_SPEED: 2},  # noqa: E501
                2: {CornerType.SLOW: 1, CornerType.MEDIUM: 1, CornerType.FAST: 1, CornerType.HIGH_SPEED: 1},  # noqa: E501
            },
            sector_straight_lengths_km=[0.5, 0.5, 0.2],
            sector_drs_zones=[1, 1, 0],
            sector_overtaking_difficulty=[20, 25, 30],
            sector_dirty_air_sensitivity=[85, 80, 75],
            sector_braking_difficulty=[70, 65, 60],
            sector_traction_demand=[40, 50, 45],
            sector_aero_dependency=[85, 80, 75],
            sector_overtaking_opportunity=[80, 75, 70],
            sector_defense_difficulty=[20, 25, 30],
            longest_straight_km=1.2,
            overtaking_difficulty=25,
            front_tyre_stress=45,
            rear_tyre_stress=40,
            lateral_energy=40,
            traction_energy=45,
            braking_energy=65,
            degradation_profile="low",
            base_degradation_rate=0.025,
            aero_sensitivity=80,
            track_evolution_rate=0.010,
            safety_car_probability=0.15,
            reference_lap_time=80.0,
            pit_stop_time_loss=24.0,
        ),
    ]
