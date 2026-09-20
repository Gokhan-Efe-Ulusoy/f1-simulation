"""Race procedures: formation lap, standing start, first corner, red flags (Phase 8).

All models are reduced-order statistical approximations. Stochastic draws
use dedicated named streams (formation/start/red_flag) so existing
Phase 1-7 streams keep their exact draw order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Formation lap
# ---------------------------------------------------------------------------

class FormationConfig(BaseModel):
    """Formation-lap coefficients (documented, validated)."""

    warmup_rate: float = Field(default=0.6, ge=0.0, le=1.0)  # fraction toward optimal temp
    optimal_tyre_temp: float = Field(default=95.0, ge=70.0, le=110.0)  # Celsius
    base_incident_probability: float = Field(default=0.002, ge=0.0, le=0.1)  # per driver
    aggression_incident_coeff: float = Field(default=0.00005, ge=0.0, le=0.001)

    model_config = {"use_enum_values": True}


@dataclass
class FormationResult:
    """Per-driver formation-lap outcome."""

    driver_id: str
    tyre_temp: float
    incident: bool = False
    failed_to_start: bool = False
    debug_info: dict[str, Any] = field(default_factory=dict)


class FormationLapModel:
    """Warms tyres/brakes and checks grid readiness."""

    def __init__(self, config: FormationConfig | None = None):
        self.config = config or FormationConfig()

    def run(
        self,
        driver_id: str,
        current_tyre_temp: float,
        aggression: float,
        reliability: float,
        rng: np.random.Generator,
    ) -> FormationResult:
        """Run the formation lap for one driver (deterministic given rng)."""
        target = self.config.optimal_tyre_temp
        tyre_temp = current_tyre_temp + (target - current_tyre_temp) * self.config.warmup_rate
        prob = self.config.base_incident_probability
        prob += aggression * self.config.aggression_incident_coeff
        prob *= 1.0 + (100.0 - reliability) / 100.0
        incident = bool(rng.random() < prob)
        failed = bool(incident and rng.random() < 0.1)
        return FormationResult(
            driver_id=driver_id,
            tyre_temp=tyre_temp,
            incident=incident,
            failed_to_start=failed,
            debug_info={"incident_probability": prob},
        )


# ---------------------------------------------------------------------------
# Standing start
# ---------------------------------------------------------------------------

class StartConfig(BaseModel):
    """Standing-start coefficients."""

    reaction_base: float = Field(default=0.25, ge=0.1, le=0.6)  # seconds
    reaction_skill_coeff: float = Field(default=0.002, ge=0.0, le=0.01)  # per skill point
    reaction_variance: float = Field(default=0.08, ge=0.0, le=0.3)  # seconds (std)
    launch_traction_weight: float = Field(default=0.5, ge=0.0, le=1.0)  # unitless
    launch_power_weight: float = Field(default=0.3, ge=0.0, le=1.0)  # unitless
    launch_aggression_bonus: float = Field(default=0.002, ge=0.0, le=0.01)
    max_gain_per_start: int = Field(default=3, ge=0, le=6)  # positions
    max_loss_per_start: int = Field(default=3, ge=0, le=6)  # positions

    model_config = {"use_enum_values": True}


@dataclass
class StartResult:
    """Per-driver standing-start outcome."""

    driver_id: str
    reaction_time: float  # seconds
    launch_quality: float  # 0-1
    position_delta: int  # +gain / -loss, bounded
    debug_info: dict[str, Any] = field(default_factory=dict)


class StandingStartModel:
    """Deterministic/probabilistic standing start."""

    def __init__(self, config: StartConfig | None = None):
        self.config = config or StartConfig()

    def evaluate(
        self,
        driver_id: str,
        start_performance: float,
        aggression: float,
        car_traction: float,
        car_power_proxy: float,
        tyre_temp: float,
        track_grip: float,
        rng: np.random.Generator,
    ) -> StartResult:
        """Evaluate one driver's launch (same seed => same result)."""
        cfg = self.config
        reaction = cfg.reaction_base
        reaction -= (start_performance - 50.0) * cfg.reaction_skill_coeff
        reaction += float(rng.normal(0.0, cfg.reaction_variance))
        reaction = max(0.1, reaction)

        launch = 0.5
        launch += (car_traction - 50.0) / 100.0 * cfg.launch_traction_weight
        launch += (car_power_proxy - 50.0) / 100.0 * cfg.launch_power_weight
        launch += (aggression - 50.0) * cfg.launch_aggression_bonus
        launch += (start_performance - 50.0) * 0.004
        if tyre_temp < 80.0:
            launch -= (80.0 - tyre_temp) * 0.004
        launch *= 0.7 + 0.3 * track_grip
        launch = float(max(0.0, min(1.0, launch)))

        # Map launch quality to a bounded position delta vs an average launch
        edge = launch - 0.5
        if edge > 0.12:
            delta = 2
        elif edge > 0.04:
            delta = 1
        elif edge < -0.12:
            delta = -2
        elif edge < -0.04:
            delta = -1
        else:
            delta = 0
        delta = max(-cfg.max_loss_per_start, min(cfg.max_gain_per_start, delta))
        return StartResult(
            driver_id=driver_id,
            reaction_time=reaction,
            launch_quality=launch,
            position_delta=delta,
            debug_info={"edge_vs_average": edge},
        )


# ---------------------------------------------------------------------------
# First corner
# ---------------------------------------------------------------------------

class FirstCornerConfig(BaseModel):
    """First-corner coefficients (conservative by design)."""

    base_contact_probability: float = Field(default=0.02, ge=0.0, le=0.3)
    aggression_coeff: float = Field(default=0.0004, ge=0.0, le=0.005)
    density_coeff: float = Field(default=0.004, ge=0.0, le=0.05)  # per nearby car
    braking_difficulty_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    wet_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    dnf_given_contact: float = Field(default=0.08, ge=0.0, le=0.5)
    damage_time_loss: tuple[float, float] = (2.0, 8.0)  # seconds range

    model_config = {"use_enum_values": True}


@dataclass
class FirstCornerOutcome:
    """First-corner outcome for one driver."""

    driver_id: str
    outcome: str  # clean | position_change | lockup | spin | contact | damage | dnf
    time_loss: float = 0.0
    positions_lost: int = 0
    debug_info: dict[str, Any] = field(default_factory=dict)


class FirstCornerModel:
    """First-corner phase with conservative incident rates."""

    def __init__(self, config: FirstCornerConfig | None = None):
        self.config = config or FirstCornerConfig()

    def evaluate(
        self,
        driver_id: str,
        grid_position: int,
        n_cars: int,
        aggression: float,
        awareness: float,
        braking_difficulty: float,
        weather: str,
        rng: np.random.Generator,
    ) -> FirstCornerOutcome:
        """Evaluate the first corner for one driver."""
        cfg = self.config
        nearby = max(0, min(6, n_cars - grid_position + 2))
        prob = cfg.base_contact_probability
        prob += aggression * cfg.aggression_coeff
        prob += nearby * cfg.density_coeff
        prob += (braking_difficulty - 50.0) / 100.0 * cfg.braking_difficulty_weight * 0.05
        prob *= 1.0 - (awareness - 50.0) / 100.0 * 0.3
        if weather in ("light_rain", "heavy_rain"):
            prob *= cfg.wet_multiplier
        elif weather in ("damp", "wet"):
            prob *= 1.3
        prob = float(max(0.0, min(0.4, prob)))

        roll = float(rng.random())
        if roll >= prob:
            return FirstCornerOutcome(driver_id=driver_id, outcome="clean",
                                      debug_info={"contact_probability": prob})
        severity = float(rng.random())
        low, high = cfg.damage_time_loss
        time_loss = low + (high - low) * float(rng.random())
        if severity < cfg.dnf_given_contact:
            return FirstCornerOutcome(driver_id=driver_id, outcome="dnf",
                                      time_loss=time_loss, positions_lost=0,
                                      debug_info={"contact_probability": prob})
        kind = "contact" if severity < 0.5 else ("lockup" if severity < 0.75 else "spin")
        lost = 1 if severity < 0.6 else 2
        return FirstCornerOutcome(driver_id=driver_id, outcome=kind,
                                  time_loss=time_loss, positions_lost=lost,
                                  debug_info={"contact_probability": prob})


# ---------------------------------------------------------------------------
# Red flag + standing restart
# ---------------------------------------------------------------------------

class RedFlagState(str):
    """Red-flag lifecycle states (plain strings for serializability)."""

    GREEN = "green"
    RED_FLAG = "red_flag"
    RESTART_PREPARATION = "restart_preparation"
    RESTART = "restart"


class RedFlagConfig(BaseModel):
    """Red-flag coefficients."""

    base_probability_per_lap: float = Field(default=0.0, ge=0.0, le=0.2)
    terminal_incident_boost: float = Field(default=0.5, ge=0.0, le=1.0)
    extreme_weather_boost: float = Field(default=0.3, ge=0.0, le=1.0)
    suspension_laps: int = Field(default=3, ge=1, le=10)
    preserve_tyre_wear: bool = True
    preserve_fuel: bool = True

    model_config = {"use_enum_values": True}


@dataclass
class RedFlagDecision:
    """Whether a red flag is thrown this lap."""

    deploy: bool
    reason: str = ""
    debug_info: dict[str, Any] = field(default_factory=dict)


class RedFlagModel:
    """Basic red-flag trigger model (rare by default)."""

    def __init__(self, config: RedFlagConfig | None = None):
        self.config = config or RedFlagConfig()

    def check(
        self,
        lap: int,
        had_terminal_incident: bool,
        extreme_weather: bool,
        rng: np.random.Generator,
    ) -> RedFlagDecision:
        """Decide whether to throw a red flag (deterministic given rng)."""
        prob = self.config.base_probability_per_lap
        reason = "race_control"
        if had_terminal_incident:
            prob += self.config.terminal_incident_boost
            reason = "major_incident"
        if extreme_weather:
            prob += self.config.extreme_weather_boost
            reason = "extreme_weather"
        prob = float(max(0.0, min(0.9, prob)))
        if float(rng.random()) < prob:
            return RedFlagDecision(deploy=True, reason=reason,
                                   debug_info={"probability": prob, "lap": lap})
        return RedFlagDecision(deploy=False, reason="",
                               debug_info={"probability": prob, "lap": lap})


class StandingRestartConfig(BaseModel):
    """Standing-restart coefficients (reuses restart physics)."""

    reaction_variance: float = Field(default=0.12, ge=0.0, le=0.3)  # seconds (std)
    start_skill_coeff: float = Field(default=0.02, ge=0.0, le=0.1)

    model_config = {"use_enum_values": True}


@dataclass
class StandingRestartResult:
    """Standing-restart outcome for one driver."""

    driver_id: str
    reaction_time: float
    position_delta: int
    debug_info: dict[str, Any] = field(default_factory=dict)


class StandingRestartModel:
    """Standing restart after a red flag (delegates to SafetyCarRestartModel)."""

    def __init__(
        self,
        config: StandingRestartConfig | None = None,
        restart_model: Any = None,
    ) -> None:
        self.config = config or StandingRestartConfig()
        self._restart_model = restart_model

    def _model(self) -> Any:
        if self._restart_model is None:
            from app.simulation.racing.safety_car_restart import SafetyCarRestartModel

            self._restart_model = SafetyCarRestartModel()
        return self._restart_model

    def evaluate(self, context: Any, rng: np.random.Generator) -> StandingRestartResult:
        """Evaluate one driver's standing restart via the shared restart model."""
        result = self._model().evaluate_restart(context, rng)
        changes = dict(result.position_change_probability or {})
        # Choose the most likely non-negative outcome conservatively
        best_delta = max(changes, key=lambda k: changes[k]) if changes else 0
        return StandingRestartResult(
            driver_id=context.driver_id,
            reaction_time=result.reaction_time,
            position_delta=int(best_delta),
            debug_info={"incident_risk": result.incident_risk},
        )
