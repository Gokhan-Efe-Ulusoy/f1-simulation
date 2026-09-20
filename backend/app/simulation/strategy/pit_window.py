"""PitWindowEngine — explicit earliest/preferred/latest calculations.

Leakage-safe: uses only current state + priors, not future realized weather/RC.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.simulation.strategy.state import StrategyState
from app.simulation.models.tyre import get_standard_tyre_specs
from app.simulation.tyre.calibration import load_tyre_observations, calibrate_degradation


@dataclass
class PitWindowResult:
    earliest_feasible_lap: int
    preferred_window_start: int
    preferred_lap: int
    preferred_window_end: int
    latest_feasible_lap: int
    pit_loss: float
    tyre_life_remaining: int
    reason: str
    evidence_tier: str = "PRIOR_ONLY"


class PitWindowEngine:
    """Calculates pit windows respecting tyre, traffic, RC, weather."""

    def __init__(self, as_of: str | None = None):
        self.as_of = as_of

    def calculate(
        self,
        state: StrategyState,
        track_pit_loss: float = 22.0,
        safety_car_active: bool = False,
        vsc_active: bool = False,
        red_flag_active: bool = False,
    ) -> PitWindowResult:
        # Tyre-driven window: optimal laps from specs or calibrated beta
        specs = get_standard_tyre_specs()
        # Try calibrated degradation for modern era
        beta = None
        evidence = "PRIOR_ONLY"
        try:
            if self.as_of:
                obs = load_tyre_observations()
                deg_model = calibrate_degradation(obs, as_of=self.as_of)
                key = state.current_compound.upper()
                if key in deg_model and deg_model[key].get("available"):
                    beta = deg_model[key]["beta"]
                    evidence = deg_model[key].get("evidence_tier", "CALIBRATED")
        except:
            pass

        # Estimate tyre life: if beta available, tyre life where deg 2.5s/lap
        # deg = beta * age => age_max = 2.5 / beta
        optimal = 20
        if beta and beta > 0:
            try:
                optimal = int(2.5 / beta)
                optimal = max(8, min(35, optimal))
            except:
                pass
        else:
            # fallback to spec max_life_laps
            try:
                spec = specs.get(state.current_compound.lower()) or specs.get("medium")
                optimal = int(getattr(spec, "max_life_laps", 20))
            except:
                optimal = 20

        # Current age influences window
        age = state.tyre_age
        remaining = max(0, optimal - age)

        # Base window centered on optimal
        # If tyre is at optimal, window is soon
        if remaining <= 3:
            preferred = state.lap + 1
            earliest = state.lap + 1
            latest = state.lap + 4
            reason = "tyre at limit"
        elif remaining <= 8:
            preferred = state.lap + remaining // 2
            earliest = state.lap + 2
            latest = state.lap + remaining
            reason = "tyre degradation increasing"
        else:
            # Mid-stint: window further out
            preferred = state.lap + remaining
            earliest = state.lap + max(3, remaining - 5)
            latest = state.lap + remaining + 5
            reason = "mid-stint"

        # Clamp to race length
        earliest = max(state.lap + 1, earliest)
        latest = min(state.lap + state.laps_remaining, latest)
        preferred = max(earliest, min(preferred, latest))
        # Ensure earliest also within race length
        earliest = min(earliest, state.lap + state.laps_remaining)
        latest = max(earliest, latest)
        preferred = max(earliest, min(preferred, latest))

        # Traffic adjustment: if gap ahead <1.5s, delay outside? simplistic: narrow window
        if state.gap_ahead > 0 and state.gap_ahead < 1.5:
            # In traffic, prefer to pit earlier to undercut
            preferred = max(earliest, preferred - 1)
            reason += " + traffic"

        # Race control adjustment: SC/VSC reduces pit loss, so window extends / prefers now
        pit_loss = track_pit_loss
        if safety_car_active:
            pit_loss *= 0.35  # SC cheap (neutralisation factor)
            preferred = state.lap  # pit now
            earliest = state.lap
            reason += " + SC opportunity"
        elif vsc_active:
            pit_loss *= 0.55
            preferred = state.lap
            earliest = state.lap
            reason += " + VSC opportunity"
        elif red_flag_active:
            pit_loss = 0.0
            reason += " + RED_FLAG"

        # Weather: if forecast rain prob >0.3 and crossover, window includes
        rain_prob = state.forecast_summary.get("rain_prob_next_5", 0) if state.forecast_summary else 0  # noqa: E501
        if rain_prob > 0.3:
            # If wetness already high, window immediate
            if state.wetness > 0.25:
                preferred = state.lap
                earliest = state.lap
                reason += " + weather crossover"
            else:
                # Extend window to allow early weather pit
                earliest = min(earliest, state.lap + 1)
                reason += " + forecast rain"

        # Fuel: if low (<10kg), must pit soon
        if state.fuel_remaining < 10:
            latest = min(latest, state.lap + 2)
            reason += " + low fuel"

        # Ensure ordering
        earliest = max(state.lap + 1, earliest) if not (safety_car_active or vsc_active) else state.lap  # noqa: E501
        if earliest > latest:
            latest = earliest
        if preferred < earliest:
            preferred = earliest
        if preferred > latest:
            preferred = latest

        return PitWindowResult(
            earliest_feasible_lap=earliest,
            preferred_window_start=max(earliest, preferred - 2),
            preferred_lap=preferred,
            preferred_window_end=min(latest, preferred + 2),
            latest_feasible_lap=latest,
            pit_loss=pit_loss,
            tyre_life_remaining=remaining,
            reason=reason,
            evidence_tier=evidence,
        )
