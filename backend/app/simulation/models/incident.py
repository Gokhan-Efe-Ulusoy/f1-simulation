from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    """Types of incidents."""

    SPIN = "spin"
    COLLISION = "collision"
    LOCKUP = "lockup"
    OFF_TRACK = "off_track"
    FRONT_WING_DAMAGE = "front_wing_damage"
    REAR_WING_DAMAGE = "rear_wing_damage"
    FLOOR_DAMAGE = "floor_damage"
    SIDEPO_DAMAGE = "sidepod_damage"
    PUNCTURE = "puncture"
    BRAKE_FAILURE = "brake_failure"
    ENGINE_FAILURE = "engine_failure"
    GEARBOX_FAILURE = "gearbox_failure"
    HYDRAULICS_FAILURE = "hydraulics_failure"
    ELECTRICAL_FAILURE = "electrical_failure"
    SUSPENSION_FAILURE = "suspension_failure"
    ERS_FAILURE = "ers_failure"
    DRIVER_ERROR = "driver_error"
    TIRE_FAILURE = "tire_failure"


class IncidentSeverity(str, Enum):
    """Incident severity."""

    MINOR = "minor"       # Small time loss, no damage
    MODERATE = "moderate" # Time loss, minor damage
    MAJOR = "major"       # Significant time loss, damage, possible retirement
    TERMINAL = "terminal" # Immediate retirement


class IncidentCause(str, Enum):
    """Root cause of incident."""

    DRIVER_MISTAKE = "driver_mistake"
    MECHANICAL = "mechanical"
    CONTACT = "contact"
    TRACK_CONDITIONS = "track_conditions"
    TIRE = "tire"
    RACING_INCIDENT = "racing_incident"


@dataclass
class Incident:
    """An incident occurrence."""

    incident_id: str
    incident_type: IncidentType
    severity: IncidentSeverity
    cause: IncidentCause

    # Participants
    driver_id: str
    other_driver_id: str | None = None

    # Timing
    lap: int = 0
    sector: int = 0
    timestamp: float = 0.0

    # Consequences
    time_loss: float = 0.0  # Seconds
    position_lost: int = 0
    is_retirement: bool = False
    retirement_reason: str | None = None

    # Damage
    aero_damage: float = 0.0  # 0-1
    mechanical_damage: float = 0.0  # 0-1
    tyre_damage: str | None = None  # Which tyre

    # Penalties
    penalty: str | None = None
    penalty_time: float = 0.0

    # Context
    was_attacking: bool = False
    was_defending: bool = False
    in_drs: bool = False
    track_condition: str = "dry"

    # Description
    description: str = ""

    model_config = {"use_enum_values": True}


class IncidentProbability(BaseModel):
    """Base probabilities for different incident types (per lap)."""

    # Driver errors
    spin: float = 0.001
    lockup: float = 0.002
    off_track: float = 0.0015
    driver_error: float = 0.0005

    # Contact
    collision: float = 0.0008

    # Mechanical
    engine_failure: float = 0.0003
    gearbox_failure: float = 0.0002
    brake_failure: float = 0.0001
    hydraulics_failure: float = 0.0001
    electrical_failure: float = 0.0001
    suspension_failure: float = 0.0001
    ers_failure: float = 0.00015

    # Aero
    front_wing_damage: float = 0.0005
    rear_wing_damage: float = 0.0002
    floor_damage: float = 0.0003
    sidepod_damage: float = 0.0002

    # Tyres
    puncture: float = 0.0004
    tire_failure: float = 0.0001

    model_config = {"use_enum_values": True}

    def get_total_probability(self) -> float:
        return sum(v for v in self.model_dump().values() if isinstance(v, float))


class IncidentModel(BaseModel):
    """Model for generating and processing incidents."""

    # Base probabilities
    base_probabilities: IncidentProbability = Field(default_factory=IncidentProbability)

    # Modifiers
    driver_mistake_multiplier: float = 1.0
    aggression_multiplier: float = 1.0
    wet_weather_multiplier: float = 2.5
    damp_weather_multiplier: float = 1.5
    high_degradation_multiplier: float = 1.5
    safety_car_multiplier: float = 0.5  # Less incidents under SC
    vsc_multiplier: float = 0.7
    first_lap_multiplier: float = 5.0
    restart_multiplier: float = 3.0

    # Severity distributions (must sum to 1.0)
    severity_distribution: dict[IncidentSeverity, float] = Field(default_factory=lambda: {
        IncidentSeverity.MINOR: 0.50,
        IncidentSeverity.MODERATE: 0.30,
        IncidentSeverity.MAJOR: 0.15,
        IncidentSeverity.TERMINAL: 0.05,
    })

    # Time loss by severity (seconds)
    time_loss_by_severity: dict[IncidentSeverity, tuple[float, float]] = Field(default_factory=lambda: {  # noqa: E501
        IncidentSeverity.MINOR: (0.5, 2.0),
        IncidentSeverity.MODERATE: (2.0, 8.0),
        IncidentSeverity.MAJOR: (10.0, 30.0),
        IncidentSeverity.TERMINAL: (0, 0),  # Immediate retirement
    })

    # Position loss by severity
    position_loss_by_severity: dict[IncidentSeverity, tuple[int, int]] = Field(default_factory=lambda: {  # noqa: E501
        IncidentSeverity.MINOR: (0, 1),
        IncidentSeverity.MODERATE: (1, 3),
        IncidentSeverity.MAJOR: (3, 8),
        IncidentSeverity.TERMINAL: (0, 0),
    })

    # Damage by incident type
    damage_by_type: dict[IncidentType, dict[str, float]] = Field(default_factory=lambda: {
        IncidentType.SPIN: {"aero": 0.0, "mechanical": 0.0, "tyre": 0.05},
        IncidentType.LOCKUP: {"aero": 0.0, "mechanical": 0.0, "tyre": 0.15},
        IncidentType.OFF_TRACK: {"aero": 0.02, "mechanical": 0.0, "tyre": 0.05},
        IncidentType.COLLISION: {"aero": 0.15, "mechanical": 0.05, "tyre": 0.1},
        IncidentType.FRONT_WING_DAMAGE: {"aero": 0.3, "mechanical": 0.0, "tyre": 0.0},
        IncidentType.REAR_WING_DAMAGE: {"aero": 0.2, "mechanical": 0.0, "tyre": 0.0},
        IncidentType.FLOOR_DAMAGE: {"aero": 0.25, "mechanical": 0.0, "tyre": 0.0},
        IncidentType.PUNCTURE: {"aero": 0.0, "mechanical": 0.0, "tyre": 1.0},
        IncidentType.ENGINE_FAILURE: {"aero": 0.0, "mechanical": 1.0, "tyre": 0.0},
        IncidentType.GEARBOX_FAILURE: {"aero": 0.0, "mechanical": 1.0, "tyre": 0.0},
        IncidentType.BRAKE_FAILURE: {"aero": 0.0, "mechanical": 0.5, "tyre": 0.0},
    })

    model_config = {"use_enum_values": True}

    def calculate_incident_probability(
        self,
        driver: Any,
        car: Any,
        track: Any,
        weather: str,
        lap: int,
        tyre_wear: float,
        in_traffic: bool,
        is_safety_car: bool,
        is_vsc: bool,
        is_restart: bool,
    ) -> float:
        """Calculate total incident probability for this driver this lap."""
        prob = self.base_probabilities.get_total_probability()

        # Driver factors
        prob *= (1.0 + (100 - driver.consistency) / 100 * 0.5)  # Consistency
        prob *= (1.0 + driver.mistake_rate / 100 * 0.5)  # Mistake rate
        prob *= (1.0 + driver.aggression / 100 * 0.3)  # Aggression

        # Car reliability
        prob *= (1.0 + (100 - car.chassis_reliability) / 100 * 2.0)

        # Tyre wear
        prob *= (1.0 + tyre_wear * self.high_degradation_multiplier)

        # Weather
        if weather in ("light_rain", "heavy_rain"):
            prob *= self.wet_weather_multiplier
        elif weather in ("damp", "wet"):
            prob *= self.damp_weather_multiplier

        # Track conditions
        track_type_val = track.track_type.value if hasattr(track.track_type, 'value') else track.track_type  # noqa: E501
        if track_type_val == "street":
            prob *= 1.2

        # Traffic
        if in_traffic:
            prob *= 1.3

        # Safety car / VSC
        if is_safety_car:
            prob *= self.safety_car_multiplier
        elif is_vsc:
            prob *= self.vsc_multiplier

        # First lap
        if lap == 0:
            prob *= self.first_lap_multiplier

        # Restart
        if is_restart:
            prob *= self.restart_multiplier

        return min(0.1, prob)  # Cap at 10% per lap

    def generate_incident(
        self,
        driver: Any,
        car: Any,
        track: Any,
        weather: str,
        lap: int,
        sector: int,
        tyre_wear: float,
        in_traffic: bool,
        is_attacking: bool = False,
        is_defending: bool = False,
        rng: Any = None,
    ) -> Incident | None:
        """Generate an incident if one occurs."""
        if rng is None:
            import numpy as np
            rng = np.random.default_rng()

        prob = self.calculate_incident_probability(
            driver, car, track, weather, lap, tyre_wear, in_traffic,
            False, False, False
        )

        if rng.random() > prob:
            return None

        # Select incident type based on weighted probabilities
        incident_type = self._select_incident_type(driver, car, track, weather,
                                                   tyre_wear, in_traffic, is_attacking, is_defending, rng)  # noqa: E501

        # Select severity
        severity = self._select_severity(incident_type, rng)

        # Determine cause
        cause = self._determine_cause(incident_type, driver, car, track, weather)

        # Calculate consequences
        time_loss = self._calculate_time_loss(severity, incident_type, rng)
        position_lost = self._calculate_position_loss(severity, rng)
        is_retirement = severity == IncidentSeverity.TERMINAL

        # Get damage
        damage = self.damage_by_type.get(incident_type, {"aero": 0.0, "mechanical": 0.0, "tyre": 0.0})  # noqa: E501

        return Incident(
            incident_id=f"INC_{driver.id}_{lap}_{sector}",
            incident_type=incident_type,
            severity=severity,
            cause=cause,
            driver_id=driver.id,
            lap=lap,
            sector=sector,
            time_loss=time_loss,
            position_lost=position_lost,
            is_retirement=is_retirement,
            retirement_reason=incident_type.value if is_retirement else None,
            aero_damage=damage.get("aero", 0.0),
            mechanical_damage=damage.get("mechanical", 0.0),
            tyre_damage="random" if damage.get("tyre", 0) > 0 else None,
            was_attacking=is_attacking,
            was_defending=is_defending,
            track_condition=weather,
            description=self._generate_description(incident_type, severity, driver.id),
        )

    def _select_incident_type(
        self,
        driver: Any,
        car: Any,
        track: Any,
        weather: str,
        tyre_wear: float,
        in_traffic: bool,
        is_attacking: bool,
        is_defending: bool,
        rng: Any,
    ) -> IncidentType:
        """Select incident type based on context."""
        weights = {}

        # Base weights from probabilities
        base = self.base_probabilities.model_dump()
        for k, v in base.items():
            if isinstance(v, float):
                weights[IncidentType(k)] = v

        # Context adjustments
        if in_traffic or is_attacking or is_defending:
            weights[IncidentType.COLLISION] *= 3.0
            weights[IncidentType.FRONT_WING_DAMAGE] *= 2.0

        if weather in ("light_rain", "heavy_rain", "damp", "wet"):
            weights[IncidentType.SPIN] *= 3.0
            weights[IncidentType.LOCKUP] *= 2.0
            weights[IncidentType.OFF_TRACK] *= 2.5

        if tyre_wear > 0.7:
            weights[IncidentType.PUNCTURE] *= 3.0
            weights[IncidentType.TIRE_FAILURE] *= 2.0

        if driver.mistake_rate > 60:
            weights[IncidentType.DRIVER_ERROR] *= 2.0

        if car.chassis_reliability < 70:
            for mech in [IncidentType.ENGINE_FAILURE, IncidentType.GEARBOX_FAILURE,
                        IncidentType.BRAKE_FAILURE, IncidentType.HYDRAULICS_FAILURE,
                        IncidentType.ELECTRICAL_FAILURE, IncidentType.SUSPENSION_FAILURE]:
                weights[mech] *= 2.0

        # Normalize and select
        total = sum(weights.values())
        roll = rng.random() * total
        cumulative = 0.0
        for inc_type, weight in weights.items():
            cumulative += weight
            if roll <= cumulative:
                return inc_type

        return IncidentType.SPIN  # Fallback

    def _select_severity(self, incident_type: IncidentType, rng: Any) -> IncidentSeverity:
        """Select severity based on distribution."""
        # Some incident types have different severity profiles
        dist = self.severity_distribution.copy()

        if incident_type in (IncidentType.ENGINE_FAILURE, IncidentType.GEARBOX_FAILURE,
                            IncidentType.SUSPENSION_FAILURE):
            # Mechanical failures more likely to be terminal
            dist[IncidentSeverity.TERMINAL] = 0.25
            dist[IncidentSeverity.MAJOR] = 0.40
            dist[IncidentSeverity.MODERATE] = 0.25
            dist[IncidentSeverity.MINOR] = 0.10
        elif incident_type == IncidentType.PUNCTURE:
            dist[IncidentSeverity.MODERATE] = 0.50
            dist[IncidentSeverity.MINOR] = 0.30
            dist[IncidentSeverity.MAJOR] = 0.20

        roll = rng.random()
        cumulative = 0.0
        for sev, prob in dist.items():
            cumulative += prob
            if roll <= cumulative:
                return sev
        return IncidentSeverity.MINOR

    def _determine_cause(
        self,
        incident_type: IncidentType,
        driver: Any,
        car: Any,
        track: Any,
        weather: str,
    ) -> IncidentCause:
        """Determine root cause."""
        mechanical_types = {
            IncidentType.ENGINE_FAILURE, IncidentType.GEARBOX_FAILURE,
            IncidentType.BRAKE_FAILURE, IncidentType.HYDRAULICS_FAILURE,
            IncidentType.ELECTRICAL_FAILURE, IncidentType.SUSPENSION_FAILURE,
            IncidentType.ERS_FAILURE,
        }
        tire_types = {IncidentType.PUNCTURE, IncidentType.TIRE_FAILURE}
        contact_types = {IncidentType.COLLISION}

        if incident_type in mechanical_types:
            return IncidentCause.MECHANICAL
        elif incident_type in tire_types:
            return IncidentCause.TIRE
        elif incident_type in contact_types:
            return IncidentCause.CONTACT
        elif weather in ("light_rain", "heavy_rain", "damp", "wet"):
            return IncidentCause.TRACK_CONDITIONS
        else:
            return IncidentCause.DRIVER_MISTAKE

    def _calculate_time_loss(
        self,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        rng: Any,
    ) -> float:
        """Calculate time loss in seconds."""
        if severity == IncidentSeverity.TERMINAL:
            return 0.0

        low, high = self.time_loss_by_severity[severity]

        # Some incidents inherently take longer
        if incident_type in (IncidentType.COLLISION, IncidentType.FRONT_WING_DAMAGE):
            low *= 1.5
            high *= 1.5
        elif incident_type == IncidentType.PUNCTURE:
            low = max(low, 10.0)  # Must pit
            high = max(high, 25.0)

        return rng.uniform(low, high)

    def _calculate_position_loss(
        self,
        severity: IncidentSeverity,
        rng: Any,
    ) -> int:
        """Calculate positions lost."""
        if severity == IncidentSeverity.TERMINAL:
            return 0

        low, high = self.position_loss_by_severity[severity]
        return rng.integers(low, high + 1)

    def _generate_description(
        self,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        driver_id: str,
    ) -> str:
        """Generate human-readable description."""
        descriptions = {
            IncidentType.SPIN: f"{driver_id} spins",
            IncidentType.LOCKUP: f"{driver_id} locks up",
            IncidentType.OFF_TRACK: f"{driver_id} runs wide",
            IncidentType.COLLISION: f"{driver_id} involved in collision",
            IncidentType.FRONT_WING_DAMAGE: f"{driver_id} damages front wing",
            IncidentType.REAR_WING_DAMAGE: f"{driver_id} damages rear wing",
            IncidentType.FLOOR_DAMAGE: f"{driver_id} sustains floor damage",
            IncidentType.PUNCTURE: f"{driver_id} suffers puncture",
            IncidentType.ENGINE_FAILURE: f"{driver_id} engine failure",
            IncidentType.GEARBOX_FAILURE: f"{driver_id} gearbox failure",
            IncidentType.BRAKE_FAILURE: f"{driver_id} brake failure",
        }
        base = descriptions.get(incident_type, f"{driver_id} incident")
        return f"{base} ({severity.value})"


# Default incident model
DEFAULT_INCIDENT_MODEL = IncidentModel()
