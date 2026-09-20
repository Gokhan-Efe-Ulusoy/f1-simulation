from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EngineMode(str, Enum):
    """Engine modes."""

    CONSERVE = "conserve"
    STANDARD = "standard"
    ATTACK = "attack"
    OVERTAKE = "overtake"
    QUALIFYING = "qualifying"


class Engine(BaseModel):
    """Formula 1 Power Unit model."""

    # Identity
    id: str
    name: str
    manufacturer: str
    supplier_id: str

    # Performance (0-100)
    peak_power_kw: float = Field(default=750, ge=600, le=850)  # ~1000-1150 HP
    energy_recovery_efficiency: float = Field(ge=0, le=100, default=80)
    ers_deployment_per_lap: float = Field(default=4.0, ge=2.0, le=5.0)  # MJ
    ers_recovery_per_lap: float = Field(default=2.0, ge=1.0, le=4.0)  # MJ

    # Characteristics
    power_curve_aggressiveness: float = Field(ge=0, le=100, default=50)  # How peaky
    torque_fill: float = Field(ge=0, le=100, default=75)  # Low-end torque
    drivability: float = Field(ge=0, le=100, default=75)

    # Fuel
    fuel_efficiency: float = Field(ge=0, le=100, default=75)  # Lower consumption
    fuel_burn_rate_base: float = Field(default=1.8, ge=1.5, le=2.5)  # kg/lap

    # Reliability
    reliability: float = Field(ge=0, le=100, default=85)
    max_race_distance_km: float = Field(default=3000, ge=2000, le=5000)

    # Modes
    mode_power_delta: dict[EngineMode, float] = Field(default_factory=lambda: {
        EngineMode.CONSERVE: -30.0,   # kW
        EngineMode.STANDARD: 0.0,
        EngineMode.ATTACK: 15.0,
        EngineMode.OVERTAKE: 25.0,
        EngineMode.QUALIFYING: 40.0,
    })
    mode_fuel_multiplier: dict[EngineMode, float] = Field(default_factory=lambda: {
        EngineMode.CONSERVE: 0.85,
        EngineMode.STANDARD: 1.0,
        EngineMode.ATTACK: 1.15,
        EngineMode.OVERTAKE: 1.25,
        EngineMode.QUALIFYING: 1.40,
    })
    mode_ers_multiplier: dict[EngineMode, float] = Field(default_factory=lambda: {
        EngineMode.CONSERVE: 0.5,
        EngineMode.STANDARD: 1.0,
        EngineMode.ATTACK: 1.2,
        EngineMode.OVERTAKE: 1.5,
        EngineMode.QUALIFYING: 1.5,
    })

    # Wear
    wear_per_race_km: float = Field(default=0.001, ge=0.0005, le=0.005)
    performance_loss_per_wear: float = Field(default=0.5, ge=0.1, le=2.0)  # kW per 1% wear

    # Upgrades
    upgrade_level: int = 0  # 0 = spec 1, increments per upgrade
    development_tokens_spent: int = 0

    model_config = {"use_enum_values": True}

    def get_power_output(self, mode: EngineMode, wear: float = 0.0) -> float:
        """Get current power output in kW."""
        base = self.peak_power_kw
        mode_delta = self.mode_power_delta.get(mode, 0.0)
        wear_loss = wear * self.performance_loss_per_wear
        return base + mode_delta - wear_loss

    def get_fuel_burn_rate(self, mode: EngineMode) -> float:
        """Get fuel burn rate in kg/lap for given mode."""
        return self.fuel_burn_rate_base * self.mode_fuel_multiplier.get(mode, 1.0)

    def get_ers_deployment(self, mode: EngineMode) -> float:
        """Get ERS deployment in MJ/lap for given mode."""
        base = self.ers_deployment_per_lap
        return base * self.mode_ers_multiplier.get(mode, 1.0)

    def get_failure_probability(self, distance_km: float, mode: EngineMode) -> float:
        """Get probability of engine failure."""
        base_rate = (100 - self.reliability) / 100 * 0.0001  # per km
        mode_factor = self.mode_fuel_multiplier.get(mode, 1.0)
        distance_factor = min(1.0, distance_km / self.max_race_distance_km)
        return base_rate * mode_factor * (1 + distance_factor)

    def get_efficiency_factor(self) -> float:
        """Get overall efficiency factor (lower = more efficient)."""
        return 1.0 - (self.fuel_efficiency - 50) / 100 * 0.2  # 0.9 to 1.1


class Car(BaseModel):
    """Formula 1 Car model with component-level performance parameters.
    
    The car is NOT reduced to a single overall rating.
    Each component affects different track types and conditions differently.
    """

    # Identity
    id: str
    name: str
    team_id: str
    engine_id: str
    year: int

    # Aerodynamics (0-100)
    overall_downforce: float = Field(ge=0, le=100, default=75)
    front_downforce: float = Field(ge=0, le=100, default=75)
    rear_downforce: float = Field(ge=0, le=100, default=75)
    aero_efficiency: float = Field(ge=0, le=100, default=75)  # Downforce/drag ratio
    drs_effectiveness: float = Field(ge=0, le=100, default=75)  # DRS delta
    dirty_air_sensitivity: float = Field(ge=0, le=100, default=50)  # How much affected by following
    front_wing_sensitivity: float = Field(ge=0, le=100, default=50)  # Front wing adjustment range

    # Mechanical (0-100)
    front_suspension: float = Field(ge=0, le=100, default=75)
    rear_suspension: float = Field(ge=0, le=100, default=75)
    mechanical_grip: float = Field(ge=0, le=100, default=75)
    traction: float = Field(ge=0, le=100, default=75)
    braking_stability: float = Field(ge=0, le=100, default=75)
    brake_bias_range: float = Field(ge=0, le=100, default=50)  # Adjustment range

    # Tyre interaction (0-100)
    tyre_wear_front: float = Field(ge=0, le=100, default=75)  # Lower = less wear
    tyre_wear_rear: float = Field(ge=0, le=100, default=75)
    tyre_warmup_speed: float = Field(ge=0, le=100, default=75)  # How fast tyres get to temp
    tyre_temperature_window: float = Field(ge=0, le=100, default=75)  # Width of optimal window
    front_rear_tyre_balance: float = Field(ge=-20, le=20, default=0)  # Positive = front bias

    # Weight and distribution
    minimum_weight_kg: float = Field(default=798, ge=750, le=850)
    weight_distribution_front: float = Field(default=45.5, ge=43, le=48)  # %
    ballast_flexibility: float = Field(default=10, ge=0, le=20)  # kg movable ballast

    # Power unit integration
    cooling_efficiency: float = Field(ge=0, le=100, default=75)
    exhaust_blowing_effect: float = Field(ge=0, le=100, default=50)
    energy_deployment_smoothness: float = Field(ge=0, le=100, default=75)

    # Reliability
    chassis_reliability: float = Field(ge=0, le=100, default=90)
    gearbox_reliability: float = Field(ge=0, le=100, default=90)
    suspension_reliability: float = Field(ge=0, le=100, default=90)

    # Setup range (how much each parameter can be adjusted)
    setup_range: dict[str, float] = Field(default_factory=lambda: {
        "front_wing": 10.0,      # degrees
        "rear_wing": 8.0,
        "front_anti_roll": 5.0,  # stiffness steps
        "rear_anti_roll": 5.0,
        "ride_height_front": 5.0,  # mm
        "ride_height_rear": 5.0,
        "brake_bias": 5.0,       # % front
        "differential_entry": 10.0,
        "differential_exit": 10.0,
        "differential_mid": 10.0,
    })

    # Track-specific performance (filled during season)
    track_performance: dict[str, dict[str, float]] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def get_cornering_performance(self, corner_type: str) -> float:
        """Get cornering performance for corner type.
        
        corner_type: "slow", "medium", "fast", "hairpin", "chicane"
        """
        if corner_type in ("slow", "hairpin"):
            return (self.front_downforce + self.rear_downforce + self.mechanical_grip + self.traction) / 4  # noqa: E501
        elif corner_type in ("medium",):
            return (self.overall_downforce + self.aero_efficiency + self.mechanical_grip) / 3
        elif corner_type in ("fast",):
            return (self.overall_downforce + self.aero_efficiency + self.rear_downforce) / 3
        elif corner_type == "chicane":
            return (self.front_suspension + self.rear_suspension + self.braking_stability + self.traction) / 4  # noqa: E501
        return self.overall_downforce

    def get_straight_line_performance(self, drs_open: bool = False) -> float:
        """Get straight line speed performance (0-100)."""
        base = 100 - (self.overall_downforce / 100 * 30)  # More downforce = more drag
        aero_bonus = self.aero_efficiency / 100 * 20
        drs_bonus = self.drs_effectiveness / 100 * 15 if drs_open else 0
        power_factor = 50  # Engine dependent, placeholder
        return min(100, base + aero_bonus + drs_bonus + power_factor * 0.5)

    def get_braking_performance(self) -> float:
        """Get braking zone performance."""
        return (self.braking_stability + self.mechanical_grip + self.front_downforce * 0.5) / 2.5

    def get_tyre_degradation_multiplier(self, axle: str) -> float:
        """Get tyre degradation multiplier for axle.
        
        Returns factor where 1.0 = average, <1.0 = less degradation, >1.0 = more.
        """
        if axle == "front":
            wear_rating = self.tyre_wear_front
        else:
            wear_rating = self.tyre_wear_rear

        # 100 = 0.8x degradation, 50 = 1.0x, 0 = 1.2x
        return 1.2 - (wear_rating / 100) * 0.4

    def get_tyre_warmup_factor(self) -> float:
        """Get tyre warmup factor (laps to reach optimal temp)."""
        # 100 = 1 lap, 50 = 2 laps, 0 = 4 laps
        return max(1.0, 4.0 - (self.tyre_warmup_speed / 100) * 3.0)

    def get_fuel_efficiency_factor(self) -> float:
        """Get fuel efficiency factor (1.0 = average)."""
        # Combines car aero efficiency and engine efficiency
        return 1.0 - (self.aero_efficiency - 50) / 100 * 0.1  # 0.95 to 1.05

    def get_drag_coefficient(self, drs_open: bool = False) -> float:
        """Get effective drag coefficient (lower = less drag)."""
        base_drag = 1.0 + (self.overall_downforce / 100) * 0.5
        if drs_open:
            base_drag -= self.drs_effectiveness / 100 * 0.3
        return base_drag

    def get_setup_sensitivity(self, parameter: str) -> float:
        """How sensitive lap time is to a setup parameter (0-1)."""
        sensitivities = {
            "front_wing": 0.02,
            "rear_wing": 0.015,
            "front_anti_roll": 0.005,
            "rear_anti_roll": 0.005,
            "ride_height_front": 0.01,
            "ride_height_rear": 0.01,
            "brake_bias": 0.003,
            "differential_entry": 0.002,
            "differential_exit": 0.002,
            "differential_mid": 0.002,
        }
        return sensitivities.get(parameter, 0.005)

    def calculate_performance_index(self, track_type: str = "balanced") -> float:
        """Calculate overall performance index for a track type.
        
        This is for UI display only - simulation uses component-level parameters.
        """
        if track_type == "high_downforce":
            weights = {
                "downforce": 0.35,
                "mechanical": 0.15,
                "power": 0.20,
                "aero_eff": 0.15,
                "tyre": 0.10,
                "reliability": 0.05,
            }
        elif track_type == "low_downforce":
            weights = {
                "downforce": 0.15,
                "mechanical": 0.15,
                "power": 0.35,
                "aero_eff": 0.25,
                "tyre": 0.05,
                "reliability": 0.05,
            }
        elif track_type == "street":
            weights = {
                "downforce": 0.20,
                "mechanical": 0.30,
                "power": 0.15,
                "aero_eff": 0.10,
                "tyre": 0.15,
                "reliability": 0.10,
            }
        else:  # balanced
            weights = {
                "downforce": 0.25,
                "mechanical": 0.20,
                "power": 0.20,
                "aero_eff": 0.15,
                "tyre": 0.10,
                "reliability": 0.10,
            }

        # Power is engine-dependent, use placeholder
        power_score = 75

        return (
            weights["downforce"] * self.overall_downforce +
            weights["mechanical"] * self.mechanical_grip +
            weights["power"] * power_score +
            weights["aero_eff"] * self.aero_efficiency +
            weights["tyre"] * ((self.tyre_wear_front + self.tyre_wear_rear) / 2) +
            weights["reliability"] * self.chassis_reliability
        )
