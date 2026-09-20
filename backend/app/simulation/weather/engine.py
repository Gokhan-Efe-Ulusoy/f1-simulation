"""WeatherEngine — deterministic, leakage-safe, scenario-aware.

Handles Historical / Counterfactual / Hypothetical / Future modes.
All transitions via WeatherTransitionModel with isolated RNG stream.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.simulation.weather.state import WeatherState, EvidenceTier
from app.simulation.weather.regime import WeatherRegime
from app.simulation.weather.environment import WetnessModel
from app.simulation.weather.transition import WeatherTransitionModel
from app.simulation.weather.calibration import load_weather_observations


WEATHER_RNG_OFFSET = 500  # isolated from driver (0), qualifying (2), reliability (3), AR1 (100)


class WeatherEngine:
    """Reference weather engine, per-as_of cached obs."""

    def __init__(self, as_of: str = "2024-03-01", seed: int = 42):
        self.as_of = as_of
        self.seed = seed
        # Load observations leakage-safe
        self.observations = load_weather_observations()
        self.filtered = [o for o in self.observations if o.get("date") and o["date"] < as_of]
        # Transition model (volatility calibrated low)
        self.transition = WeatherTransitionModel(volatility=0.1)

    def initial_state_for_scenario(self, scenario: Any) -> WeatherState:
        """Resolve initial weather for scenario respecting mode & overrides."""
        # Counterfactual / hypothetical override takes precedence
        mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
        weather_override = mods.get("weather")
        if weather_override:
            # weather_override may be dict with fields like rainfall_mm_h, air_temperature_c, etc.
            # Treat as ESTIMATED / counterfactual
            base = WeatherState.fallback_prior(timestamp=getattr(scenario, "as_of", None))
            for k, v in weather_override.items():
                if hasattr(base, k):
                    setattr(base, k, v)
            base.evidence_tier = EvidenceTier.ESTIMATED
            base.per_field_tier = {k: EvidenceTier.ESTIMATED for k in weather_override.keys()}
            base.provenance = {"source": "counterfactual_override", "scenario": scenario.scenario_id}  # noqa: E501
            base.weather_regime = WeatherRegime.derive(base).value
            return base

        # Historical mode: try to find observed weather < as_of for this race_id/session
        # For simplicity, use most recent observation < as_of for that season if any
        try:
            season = int(scenario.season_id)
        except:
            season = None
        race_id = getattr(scenario, "scenario_id", "")  # e.g., "1950-british" or "2024-bahrain"
        # Search filtered for same season race
        candidates = [o for o in self.filtered if o.get("race_id") == race_id]
        if not candidates and season is not None:
            # fallback: any obs for season < as_of
            candidates = [o for o in self.filtered if o.get("season") == season]
        if candidates:
            # Take latest by date
            candidates.sort(key=lambda x: x.get("date", ""))
            latest = candidates[-1]
            ws = WeatherState.from_observed(
                air_temperature_c=latest.get("air_temperature_c"),
                track_temperature_c=latest.get("track_temperature_c"),
                humidity_pct=latest.get("humidity_pct"),
                pressure_hpa=latest.get("pressure_hpa"),
                wind_speed_mps=latest.get("wind_speed_mps"),
                wind_direction_deg=latest.get("wind_direction_deg"),
                rainfall_mm_h=latest.get("rainfall_mm_h", 0.0),
                track_wetness=0.0 if latest.get("rainfall_mm_h", 0) == 0 else 0.3,
                timestamp=latest.get("timestamp"),
                race_id=latest.get("race_id"),
                session_id=latest.get("session_key"),
                source="openf1",
            )
            # Check track temp availability; if None after from_observed, set ESTIMATED fallback
            if ws.track_temperature_c is None and ws.air_temperature_c is not None:
                ws.track_temperature_c = ws.air_temperature_c + 10.0
                ws.per_field_tier["track_temperature_c"] = EvidenceTier.ESTIMATED
            ws.weather_regime = WeatherRegime.derive(ws).value
            return ws

        # No observation under as_of → PRIOR_ONLY fallback (historical honesty)
        # For 1950-2022, this is expected NON_IDENTIFIABLE, but we still return prior dry
        ws = WeatherState.fallback_prior(timestamp=getattr(scenario, "as_of", None))
        # Mark historical as PRIOR_ONLY (not OBSERVED)
        if season is not None and season < 2023:
            ws.evidence_tier = EvidenceTier.NON_IDENTIFIABLE if season < 2015 else EvidenceTier.PRIOR_ONLY  # noqa: E501
            ws.per_field_tier = {k: EvidenceTier.NON_IDENTIFIABLE if season < 2015 else EvidenceTier.PRIOR_ONLY for k in ws.per_field_tier}  # noqa: E501
        ws.weather_regime = WeatherRegime.derive(ws).value
        return ws

    def trajectory_for_simulation(
        self, initial: WeatherState, sim_idx: int, laps: int, seed: int | None = None
    ) -> list[WeatherState]:
        """Generate deterministic weather trajectory for one simulation."""
        s = seed if seed is not None else self.seed
        rng_seed = s + sim_idx * 1000 + WEATHER_RNG_OFFSET
        rng = np.random.default_rng(rng_seed)
        traj: list[WeatherState] = []
        cur = initial
        for lap in range(laps):
            traj.append(cur)
            cur = self.transition.step(cur, rng, lap=lap)
        return traj

    def batch_trajectories(
        self, initial: WeatherState, N: int, laps: int, seed: int | None = None
    ) -> list[list[WeatherState]]:
        return [self.trajectory_for_simulation(initial, i, laps, seed=seed) for i in range(N)]
