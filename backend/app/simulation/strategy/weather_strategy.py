"""Weather Strategy — forecast-aware, leakage-safe, PRIOR_ONLY where needed."""
from __future__ import annotations

from typing import Any


class WeatherStrategyEngine:
    def __init__(self):
        pass

    def should_crossover(
        self, wetness: float, rainfall: float, forecast_rain_prob: float, current_compound: str
    ) -> tuple[bool, str, str]:
        """Decide if should switch to intermediate/wet.

        Returns (should_switch, target_compound, reason, tier)
        """
        if wetness > 0.30 and current_compound in ("soft", "medium", "hard"):
            return True, "intermediate", "wetness crossover", "PRIOR_ONLY"
        if forecast_rain_prob > 0.5 and wetness > 0.15:
            return True, "intermediate", "forecast rain", "PRIOR_ONLY"
        if rainfall > 7.5:
            return True, "wet", "heavy rain", "PRIOR_ONLY"
        return False, current_compound, "stay slick", "PRIOR_ONLY"
