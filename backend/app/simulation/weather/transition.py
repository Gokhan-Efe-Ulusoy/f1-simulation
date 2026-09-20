"""Weather state transitions — deterministic, RNG-controlled, temporally persistent.

Weather is persistent; transitions driven by process, not independent random jumps.
Uses isolated weather RNG stream (seed + sim_idx*1000 + weather_stream + lap).
"""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from app.simulation.weather.state import WeatherState, RainfallIntensity, EvidenceTier
from app.simulation.weather.regime import WeatherRegime
from app.simulation.weather.environment import WetnessModel


class WeatherTransitionModel(BaseModel):
    """Deterministic weather evolution with seeded stochastic transitions.

    All randomness via supplied numpy Generator; no global state.
    """

    wetness_model: WetnessModel = Field(default_factory=WetnessModel)
    volatility: float = Field(default=0.1, ge=0, le=1)  # overall stochastic amplitude
    persistence: float = Field(default=0.85, ge=0, le=1)  # currently unused, placeholder for AR
    rain_start_base_prob: float = Field(default=0.01, ge=0, le=1)
    rain_stop_prob: float = Field(default=0.05, ge=0, le=1)
    cloud_cover_base: float = Field(default=0.5, ge=0, le=1)

    model_config = {"arbitrary_types_allowed": True}

    def step(self, state: WeatherState, rng: np.random.Generator, lap: int, cars_on_track: int = 20) -> WeatherState:  # noqa: E501
        """Evolve one lap deterministically given rng."""
        ns = state.model_copy(deep=True)

        # Temperature drift (small)
        if ns.air_temperature_c is not None:
            ns.air_temperature_c += float(rng.normal(0, 0.2) * self.volatility)
            ns.air_temperature_c = max(-10, min(50, ns.air_temperature_c))
            # Track temp follows air with lag
            if ns.track_temperature_c is None:
                ns.track_temperature_c = ns.air_temperature_c + 10
            else:
                target = ns.air_temperature_c + 10
                ns.track_temperature_c += (target - ns.track_temperature_c) * 0.1
                ns.track_temperature_c += float(rng.normal(0, 0.15) * self.volatility)
                ns.track_temperature_c = max(-5, min(65, ns.track_temperature_c))

        # Humidity
        if ns.humidity_pct is not None:
            ns.humidity_pct = max(0, min(100, ns.humidity_pct + float(rng.normal(0, 1.0) * self.volatility)))  # noqa: E501

        # Wind
        if ns.wind_speed_mps is not None:
            ns.wind_speed_mps = max(0, ns.wind_speed_mps + float(rng.normal(0, 0.5) * self.volatility))  # noqa: E501
        if ns.wind_direction_deg is not None:
            ns.wind_direction_deg = (ns.wind_direction_deg + float(rng.normal(0, 10))) % 360

        # Pressure drift tiny
        if ns.pressure_hpa is not None:
            ns.pressure_hpa = max(900, min(1100, ns.pressure_hpa + float(rng.normal(0, 0.3) * self.volatility)))  # noqa: E501

        # Wetness evolution (phenomenological)
        ns.track_wetness = self.wetness_model.step(ns.track_wetness, ns, cars_on_track=cars_on_track)  # noqa: E501

        # Rainfall amount evolves if raining
        if ns.rainfall_mm_h is not None and ns.rainfall_mm_h > 0:
            ns.rainfall_mm_h = max(0, ns.rainfall_mm_h + float(rng.normal(0, ns.rainfall_mm_h * 0.15)))  # noqa: E501
            # Update intensity
            if ns.rainfall_mm_h <= 0:
                ns.rainfall_intensity = RainfallIntensity.NONE
            elif ns.rainfall_mm_h < 2.5:
                ns.rainfall_intensity = RainfallIntensity.LIGHT
            elif ns.rainfall_mm_h < 7.5:
                ns.rainfall_intensity = RainfallIntensity.MODERATE
            else:
                ns.rainfall_intensity = RainfallIntensity.HEAVY

        # Rain start / stop transitions (deterministic given rng)
        roll = float(rng.random())
        is_rain = ns.rainfall_mm_h is not None and ns.rainfall_mm_h > 0
        if not is_rain:
            prob = self._rain_start_prob(ns)
            if roll < prob * self.volatility:
                ns.rainfall_mm_h = float(rng.uniform(0.5, 3.0))
                ns.rainfall_intensity = RainfallIntensity.LIGHT
        else:
            # Stop prob larger if light rain
            rh = ns.rainfall_mm_h or 1
            stop = self.rain_stop_prob * (1 - min(1, rh / 20))
            if roll < stop:
                ns.rainfall_mm_h = 0.0
                ns.rainfall_intensity = RainfallIntensity.NONE

        # Re-derive wetness after rain change? keep as is; wetness already stepped
        # Derive regime
        ns.weather_regime = WeatherRegime.derive(ns).value

        return ns

    def _rain_start_prob(self, state: WeatherState) -> float:
        base = self.rain_start_base_prob
        if state.humidity_pct is not None:
            base += (state.humidity_pct / 100) * 0.05
        if state.pressure_hpa is not None and state.pressure_hpa < 1000:
            base += (1000 - state.pressure_hpa) * 0.0002
        base += self.cloud_cover_base * 0.02
        return min(0.15, base)
