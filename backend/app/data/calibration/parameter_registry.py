"""Parameter registry: calibratable simulator parameters (Phase 11).

Every parameter has name, unit, bounds, default, group and identifiability
status. Non-identifiable parameters stay at prior/default.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Identifiability(str, Enum):
    IDENTIFIABLE = "identifiable"
    WEAKLY_IDENTIFIABLE = "weakly_identifiable"
    NON_IDENTIFIABLE = "non_identifiable"


class ParameterSpec(BaseModel):
    """One calibratable parameter."""

    name: str
    group: str = ""  # lap_time, racing, tyres, weather, strategy
    unit: str = ""  # e.g. "seconds per 10kg", "seconds", "1"
    default: float
    bounds: tuple[float, float] = Field(description="(low, high)")
    description: str = ""
    identifiability: Identifiability = Identifiability.IDENTIFIABLE

    model_config = {"use_enum_values": True}


# Curated registry: only parameters with identifiable evidence are
# marked IDENTIFIABLE; correlated pairs (driver_skill vs car_performance)
# are flagged NON_IDENTIFIABLE and remain at prior.
REGISTRY: list[ParameterSpec] = [
    # Lap time
    ParameterSpec(name="fuel_time_delta", group="lap_time", unit="seconds per 10kg",
                  default=0.35, bounds=(0.1, 0.8), description="Fuel load penalty per 10kg",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="tyre_compound_delta", group="lap_time", unit="seconds",
                  default=0.8, bounds=(0.2, 2.0), description="Soft vs medium delta",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="tyre_age_degradation", group="lap_time", unit="seconds per lap",
                  default=0.05, bounds=(0.01, 0.2), description="Linear tyre wear per lap",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="cliff_threshold", group="tyres", unit="wear fraction",
                  default=0.85, bounds=(0.6, 0.95), description="Wear where cliff starts",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="weather_penalty", group="lap_time", unit="seconds",
                  default=1.5, bounds=(0.5, 4.0), description="Rain lap time penalty",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="track_wetness_penalty", group="weather", unit="seconds",
                  default=1.0, bounds=(0.2, 3.0), description="Wet track grip loss",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="traffic_penalty", group="lap_time", unit="seconds",
                  default=0.3, bounds=(0.0, 1.0), description="In-traffic loss",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="dirty_air_penalty", group="racing", unit="seconds",
                  default=0.15, bounds=(0.05, 0.5), description="Dirty air base loss",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="track_evolution", group="lap_time", unit="seconds per lap",
                  default=0.02, bounds=(0.005, 0.08), description="Track rubbers in",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="driver_variance", group="lap_time", unit="seconds",
                  default=0.5, bounds=(0.1, 1.5), description="Driver lap variance",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="driver_consistency_effect", group="lap_time", unit="seconds",
                  default=0.3, bounds=(0.0, 1.0), description="Consistency effect",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    # Racing
    ParameterSpec(name="drs_effectiveness", group="racing", unit="seconds",
                  default=0.3, bounds=(0.1, 0.6), description="DRS time gain",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="dirty_air_coeff", group="racing", unit="1",
                  default=0.015, bounds=(0.005, 0.03), description="Dirty air coeff",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="battle_persistence", group="racing", unit="laps",
                  default=5.0, bounds=(2.0, 10.0), description="Battle duration",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="incident_base_prob", group="racing", unit="probability",
                  default=0.02, bounds=(0.005, 0.05), description="Base incident prob",
                  identifiability=Identifiability.IDENTIFIABLE),
    # Tyres
    ParameterSpec(name="warmup_rate", group="tyres", unit="1 per lap",
                  default=0.5, bounds=(0.2, 1.0), description="Tyre warmup per lap",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="cooling_rate", group="tyres", unit="1 per lap",
                  default=0.3, bounds=(0.1, 0.6), description="Tyre cooling",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="degradation_rate", group="tyres", unit="seconds per lap",
                  default=0.05, bounds=(0.01, 0.2), description="Base degradation",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="cliff_behavior", group="tyres", unit="multiplier",
                  default=2.0, bounds=(1.2, 4.0), description="Cliff severity",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    # Weather
    ParameterSpec(name="rain_transition_prob", group="weather", unit="probability",
                  default=0.1, bounds=(0.01, 0.3), description="Rain start prob",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="wetness_accumulation", group="weather", unit="wetness per mm/hr",
                  default=0.01, bounds=(0.001, 0.05), description="Wetness per rain",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    ParameterSpec(name="drying_rate", group="weather", unit="wetness per lap",
                  default=0.02, bounds=(0.005, 0.1), description="Drying per lap",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="crossover_threshold", group="tyres", unit="wetness 0-1",
                  default=0.25, bounds=(0.1, 0.5), description="Slick->inter threshold",
                  identifiability=Identifiability.IDENTIFIABLE),
    # Strategy
    ParameterSpec(name="pit_loss", group="strategy", unit="seconds",
                  default=22.0, bounds=(15.0, 30.0), description="Pit stop loss",
                  identifiability=Identifiability.IDENTIFIABLE),
    ParameterSpec(name="undercut_effect", group="strategy", unit="seconds",
                  default=1.5, bounds=(0.5, 3.0), description="Undercut gain",
                  identifiability=Identifiability.WEAKLY_IDENTIFIABLE),
    # Correlated / non-identifiable examples (stay at prior)
    ParameterSpec(name="driver_skill", group="lap_time", unit="0-100",
                  default=75.0, bounds=(50.0, 95.0), description="Driver skill (confounded with car)",  # noqa: E501
                  identifiability=Identifiability.NON_IDENTIFIABLE),
    ParameterSpec(name="car_performance", group="lap_time", unit="0-100",
                  default=75.0, bounds=(50.0, 95.0), description="Car performance (confounded with driver)",  # noqa: E501
                  identifiability=Identifiability.NON_IDENTIFIABLE),
]


def get_registry() -> dict[str, ParameterSpec]:
    """Name -> spec mapping (deterministic)."""
    return {p.name: p for p in REGISTRY}


def identifiable_params() -> list[ParameterSpec]:
    """Only strongly identifiable parameters."""
    return [p for p in REGISTRY if p.identifiability == Identifiability.IDENTIFIABLE]


def all_param_names() -> list[str]:
    """Sorted parameter names for stable ordering."""
    return sorted(p.name for p in REGISTRY)
