"""Weather regimes — canonical, derived from state (not arbitrarily chosen)."""
from __future__ import annotations

from enum import Enum

from app.simulation.weather.state import WeatherState, RainfallIntensity


class WeatherRegime(str, Enum):
    DRY = "DRY"
    DAMP = "DAMP"
    WET = "WET"
    HEAVY_RAIN = "HEAVY_RAIN"
    DRYING = "DRYING"

    @staticmethod
    def derive(state: WeatherState) -> "WeatherRegime":
        """Derive regime from wetness + rainfall.

        Deterministic, no randomness. Downstream code must not arbitrarily select regime.
        """
        rain = state.rainfall_mm_h if state.rainfall_mm_h is not None else 0.0
        w = state.track_wetness
        # Heavy rain overrides wetness
        if rain >= 7.5:
            return WeatherRegime.HEAVY_RAIN
        if rain > 0:
            # Any rain + wet track = WET, light rain + low wetness = DAMP
            if w >= 0.5:
                return WeatherRegime.WET
            if w >= 0.1:
                return WeatherRegime.DAMP
            return WeatherRegime.WET  # raining, treat as wet even if wetness low initially
        # No rain — dryness vs residual wetness
        if w >= 0.5:
            return WeatherRegime.WET
        if w >= 0.1:
            return WeatherRegime.DAMP
        if w > 0.01:
            return WeatherRegime.DRYING
        return WeatherRegime.DRY

    @staticmethod
    def grip_factor(regime: "WeatherRegime", wetness: float) -> float:
        # Continuous grip via state is preferred; this is discrete helper
        mapping = {
            WeatherRegime.DRY: 1.0,
            WeatherRegime.DRYING: 0.96,
            WeatherRegime.DAMP: 0.88,
            WeatherRegime.WET: 0.72,
            WeatherRegime.HEAVY_RAIN: 0.55,
        }
        base = mapping.get(regime, 1.0)
        # Adjust with wetness within regime (small slope)
        return max(0.4, base - wetness * 0.05)
