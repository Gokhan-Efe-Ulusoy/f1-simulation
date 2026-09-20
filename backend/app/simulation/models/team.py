from __future__ import annotations

from pydantic import BaseModel, Field


class Team(BaseModel):
    """Formula 1 Team/Constructor model."""

    # Identity
    id: str
    name: str
    full_name: str
    base_country: str
    team_color: str = "#FF0000"  # Hex color
    secondary_color: str = "#FFFFFF"

    # Technical
    engine_supplier_id: str
    technical_director: str | None = None
    team_principal: str | None = None

    # Performance factors (0-100 scale)
    overall_performance: float = Field(ge=0, le=100, default=75)
    chassis_quality: float = Field(ge=0, le=100, default=75)
    aero_efficiency: float = Field(ge=0, le=100, default=75)
    high_downforce_performance: float = Field(ge=0, le=100, default=75)
    low_downforce_performance: float = Field(ge=0, le=100, default=75)
    mechanical_grip: float = Field(ge=0, le=100, default=75)

    # Operational
    pit_crew_skill: float = Field(ge=0, le=100, default=80)
    strategy_quality: float = Field(ge=0, le=100, default=75)
    development_rate: float = Field(ge=0, le=100, default=50)  # How fast they improve
    reliability: float = Field(ge=0, le=100, default=85)

    # Financial
    budget_millions: float = 150.0
    cost_cap_margin: float = 10.0  # Millions under/over cap

    # Facilities
    wind_tunnel_quality: float = Field(ge=0, le=100, default=75)
    cfd_capacity: float = Field(ge=0, le=100, default=75)
    simulator_quality: float = Field(ge=0, le=100, default=75)

    # Drivers
    driver_ids: list[str] = Field(default_factory=list)
    reserve_driver_ids: list[str] = Field(default_factory=list)

    # History
    championships_won: int = 0
    wins: int = 0
    podiums: int = 0
    poles: int = 0

    # Current season
    constructor_points: float = 0.0
    constructor_position: int = 10

    # Metadata
    founded_year: int = 1950
    is_customer_team: bool = False

    model_config = {"use_enum_values": True}

    def get_track_suitability(self, track_type: str) -> float:
        """Get team's suitability for a track type.
        
        track_type: "high_downforce", "low_downforce", "street", "power", "balanced"
        """
        if track_type == "high_downforce":
            return self.high_downforce_performance
        elif track_type == "low_downforce":
            return self.low_downforce_performance
        elif track_type == "street":
            return self.mechanical_grip
        elif track_type == "power":
            return self.overall_performance * 0.9  # Engine dependent
        else:
            return self.overall_performance

    def get_pit_stop_time_base(self) -> float:
        """Get base pit stop time in seconds."""
        # Better pit crew = faster stops
        base = 2.5
        skill_factor = (100 - self.pit_crew_skill) / 100 * 0.8  # 0 to 0.8s
        return base + skill_factor

    def get_reliability_failure_rate(self) -> float:
        """Get per-lap mechanical failure probability."""
        # 85 reliability = 0.001% per lap, 50 = 0.1% per lap
        return max(0.00001, (100 - self.reliability) / 100 * 0.001)

    def get_development_points_per_race(self) -> float:
        """Get development points earned per race weekend."""
        return self.development_rate / 100 * 10  # 0-10 points


class TeamStats(BaseModel):
    """Season statistics for a team."""

    team_id: str
    season: int
    points: float = 0.0
    wins: int = 0
    podiums: int = 0
    poles: int = 0
    fastest_laps: int = 0
    dnfs: int = 0
    avg_pit_stop_time: float = 2.5
    development_points: float = 0.0

    model_config = {"use_enum_values": True}
