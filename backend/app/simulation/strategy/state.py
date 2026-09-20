"""StrategyState — immutable observable view at decision time t.

Only information available at lap t is included. No future arrays.
Evidence tiers per field where appropriate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceTier(str, Enum):
    OBSERVED = "OBSERVED"
    CALIBRATED = "CALIBRATED"
    LIMITED = "LIMITED"
    PRIOR_ONLY = "PRIOR_ONLY"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    ESTIMATED = "ESTIMATED"
    KNOWN = "KNOWN"


class StrategyState(BaseModel):
    """Leakage-safe view at lap t.

    All fields are observable at current lap, not future.
    """

    # identification
    driver_id: str
    lap: int
    position: int
    gap_ahead: float = 0.0
    gap_behind: float = 0.0

    # tyre
    current_compound: str = "medium"
    tyre_age: int = 0
    stint_index: int = 0
    available_compounds: list[str] = Field(default_factory=lambda: ["soft", "medium", "hard"])

    # fuel
    fuel_remaining: float = 50.0
    fuel_delta_per_lap: float = 1.8
    fuel_target: float = 5.0

    # race control (only current lap)
    race_control_phase: str = "GREEN"  # GREEN, YELLOW, VSC, SAFETY_CAR, RED_FLAG, RESTART
    sector_flags: list[str] = Field(default_factory=lambda: ["GREEN", "GREEN", "GREEN"])

    # weather (only current + forecast representation, not future realized)
    weather_regime: str = "DRY"
    wetness: float = 0.0
    rainfall: float = 0.0
    track_temperature: float = 35.0
    forecast_summary: dict[str, Any] = Field(default_factory=dict)  # e.g., {"rain_prob_next_5": 0.1}  # noqa: E501
    forecast_uncertainty: float = 0.15

    # performance
    driver_pace: float | None = None  # estimated pace delta, if known
    constructor_pace: float | None = None
    estimated_degradation: float | None = None  # sec/lap
    estimated_tyre_performance: float | None = None

    # pit
    pit_loss_estimate: float = 22.0
    laps_remaining: int = 50
    completed_pit_stops: int = 0
    planned_stops: list[dict[str, Any]] = Field(default_factory=list)

    # opponents (observable only, not future actions)
    opponent_states: list[dict[str, Any]] = Field(default_factory=list)
    # each: {driver_id, gap, tyre_age, compound, pace_delta}

    # available actions (filled by decision engine, but state carries what is observable)
    available_actions: list[str] = Field(default_factory=list)

    # evidence tiers per field
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY
    per_field_tier: dict[str, EvidenceTier] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# Helper to build StrategyState from existing DriverState / RaceState / WeatherState / BatchState
def build_strategy_state_from_driver(
    driver_id: str,
    lap: int,
    position: int,
    gap_ahead: float,
    gap_behind: float,
    current_compound: str,
    tyre_age: int,
    fuel_remaining: float,
    race_control_phase: str,
    sector_flags: list[str] | None = None,
    weather_regime: str = "DRY",
    wetness: float = 0.0,
    rainfall: float = 0.0,
    track_temperature: float = 35.0,
    forecast_summary: dict | None = None,
    pit_loss_estimate: float = 22.0,
    laps_remaining: int = 58,
    opponent_states: list[dict] | None = None,
    evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
) -> StrategyState:
    return StrategyState(
        driver_id=driver_id,
        lap=lap,
        position=position,
        gap_ahead=gap_ahead,
        gap_behind=gap_behind,
        current_compound=current_compound,
        tyre_age=tyre_age,
        fuel_remaining=fuel_remaining,
        race_control_phase=race_control_phase,
        sector_flags=sector_flags or ["GREEN", "GREEN", "GREEN"],
        weather_regime=weather_regime,
        wetness=wetness,
        rainfall=rainfall,
        track_temperature=track_temperature,
        forecast_summary=forecast_summary or {},
        pit_loss_estimate=pit_loss_estimate,
        laps_remaining=laps_remaining,
        opponent_states=opponent_states or [],
        evidence_tier=evidence_tier,
    )
