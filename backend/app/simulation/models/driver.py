from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DriverSkill(str, Enum):
    """Named driver skills."""

    OVERALL = "overall_skill"
    QUALIFYING = "qualifying_skill"
    RACE = "race_skill"
    CONSISTENCY = "consistency"
    AGGRESSION = "aggression"
    TYRE_MANAGEMENT = "tyre_management"
    WET_WEATHER = "wet_weather_skill"
    OVERTAKING = "overtaking"
    DEFENDING = "defending"
    START = "start_performance"
    ADAPTABILITY = "adaptability"
    PRESSURE = "pressure_resistance"
    MISTAKE_RATE = "mistake_rate"


class Driver(BaseModel):
    """Formula 1 Driver model with detailed skill parameters.
    
    All skills use a 0-100 scale where:
    - 0-20: Rookie/Backmarker level
    - 20-40: Lower midfield
    - 40-60: Midfield
    - 60-80: Upper midfield / Race winner
    - 80-90: Championship contender
    - 90-100: All-time great
    """

    # Identity
    id: str
    name: str
    short_name: str  # 3-letter code (VER, HAM, LEC)
    number: int
    nationality: str
    date_of_birth: str  # ISO format

    # Team
    team_id: str

    # Core skills (0-100)
    overall_skill: float = Field(ge=0, le=100, default=75)
    qualifying_skill: float = Field(ge=0, le=100, default=75)
    race_skill: float = Field(ge=0, le=100, default=75)
    consistency: float = Field(ge=0, le=100, default=75)
    aggression: float = Field(ge=0, le=100, default=50)
    tyre_management: float = Field(ge=0, le=100, default=75)
    wet_weather_skill: float = Field(ge=0, le=100, default=75)
    overtaking: float = Field(ge=0, le=100, default=75)
    defending: float = Field(ge=0, le=100, default=75)
    start_performance: float = Field(ge=0, le=100, default=75)
    adaptability: float = Field(ge=0, le=100, default=75)
    pressure_resistance: float = Field(ge=0, le=100, default=75)
    mistake_rate: float = Field(ge=0, le=100, default=25)  # Lower is better

    # Form and experience
    current_form: float = Field(ge=-1, le=1, default=0.0)  # -1 to +1
    experience: int = Field(ge=0, default=50)  # 0-100

    # Track preferences
    preferred_tracks: list[str] = Field(default_factory=list)
    disliked_tracks: list[str] = Field(default_factory=list)

    # Physical
    height_cm: int = 180
    weight_kg: int = 70

    # Contract
    contract_until: int | None = None
    salary_millions: float | None = None

    # Metadata
    is_rookie: bool = False
    is_reserve: bool = False

    @field_validator('short_name')
    @classmethod
    def validate_short_name(cls, v: str) -> str:
        return v.upper()[:3]

    @field_validator('number')
    @classmethod
    def validate_number(cls, v: int) -> int:
        if not 0 <= v <= 99:
            raise ValueError('Driver number must be 0-99')
        return v

    def get_skill(self, skill: DriverSkill) -> float:
        """Get a specific skill value."""
        return getattr(self, skill.value)

    def get_effective_skill(
        self,
        track_id: str,
        weather: str,
        session_type: str,
        pressure: float = 0.0,
    ) -> float:
        """Calculate effective skill for given conditions.
        
        Base ability + current form + track suitability + conditions + pressure + small stochastic
        """
        # Base skill depends on session type
        if session_type == "qualifying":
            base = self.qualifying_skill
        elif session_type == "race":
            base = self.race_skill
        else:
            base = self.overall_skill

        # Current form (-1 to +1) scaled to ~5 points
        form_bonus = self.current_form * 5

        # Track suitability
        track_bonus = 0.0
        if track_id in self.preferred_tracks:
            track_bonus = 3.0
        elif track_id in self.disliked_tracks:
            track_bonus = -3.0

        # Weather suitability
        weather_bonus = 0.0
        if weather in ("wet", "light_rain", "heavy_rain", "intermediate"):
            weather_bonus = (self.wet_weather_skill - 50) * 0.1

        # Pressure effect
        pressure_effect = 0.0
        if pressure > 0:
            pressure_effect = -(100 - self.pressure_resistance) * pressure * 0.05

        # Mistake rate reduces consistency under pressure
        mistake_penalty = self.mistake_rate * pressure * 0.02

        effective = base + form_bonus + track_bonus + weather_bonus + pressure_effect - mistake_penalty  # noqa: E501

        # Clamp to reasonable range
        return max(0, min(100, effective))

    def get_overtaking_skill(self, pressure: float = 0.0) -> float:
        """Get overtaking skill adjusted for pressure."""
        base = self.overtaking
        pressure_effect = -(100 - self.pressure_resistance) * pressure * 0.03
        return max(0, min(100, base + pressure_effect))

    def get_defending_skill(self, pressure: float = 0.0) -> float:
        """Get defending skill adjusted for pressure."""
        base = self.defending
        pressure_effect = -(100 - self.pressure_resistance) * pressure * 0.03
        return max(0, min(100, base + pressure_effect))

    def get_tyre_management_factor(self) -> float:
        """Get tyre management factor (1.0 = average, >1.0 = better)."""
        return 0.8 + (self.tyre_management / 100) * 0.4  # 0.8 to 1.2

    def get_consistency_factor(self) -> float:
        """Get consistency factor for lap time variation."""
        # Higher consistency = lower standard deviation
        return 0.5 + (self.consistency / 100) * 0.5  # 0.5 to 1.0

    def get_mistake_probability(self, base_rate: float, pressure: float = 0.0) -> float:
        """Get probability of making a mistake this lap."""
        # Base rate modified by driver's mistake tendency and pressure
        pressure_mult = 1.0 + pressure * 0.5
        driver_mult = 0.5 + (self.mistake_rate / 100) * 1.5  # 0.5 to 2.0
        return base_rate * pressure_mult * driver_mult


class DriverStats(BaseModel):
    """Career statistics for a driver."""

    driver_id: str
    seasons: int = 0
    races: int = 0
    wins: int = 0
    podiums: int = 0
    poles: int = 0
    fastest_laps: int = 0
    championships: int = 0
    points: float = 0.0
    dnfs: int = 0
    avg_finish_position: float = 10.0
    avg_qualifying_position: float = 10.0
    win_rate: float = 0.0
    podium_rate: float = 0.0

    model_config = {"use_enum_values": True}
