"""Track wetness & environment models.

wetness(t+1) = clamp( wetness(t) + rainfall_input - drying_rate , 0,1 )
drying depends on track T, air T, wind, humidity.

Phenomenological, calibrated where possible; prior elsewhere.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.simulation.weather.state import WeatherState


class WetnessModel(BaseModel):
    """Phenomenological wetness evolution."""

    # Wetting per mm/h per lap (tuned to OpenF1: 1mm/h ~ 0.01 wetness per lap)
    rain_accumulation_rate: float = Field(default=0.01, ge=0.001, le=0.05)
    # Base drying per lap when dry (0.02 = 50 laps to dry from 1.0)
    base_drying_rate: float = Field(default=0.02, ge=0.005, le=0.1)
    wind_drying_factor: float = Field(default=0.02, ge=0, le=0.1)  # per m/s
    temp_drying_factor: float = Field(default=0.01, ge=0, le=0.05)  # per °C above 20
    humidity_drying_penalty: float = Field(default=0.005, ge=0, le=0.02)  # per % humidity

    def step(self, current_wetness: float, state: WeatherState, cars_on_track: int = 20) -> float:
        """Evolve wetness one lap deterministically."""
        w = max(0.0, min(1.0, float(current_wetness)))
        rain = state.rainfall_mm_h if state.rainfall_mm_h is not None else 0.0
        if rain > 0:
            # Rainfall adds
            inc = rain * self.rain_accumulation_rate
            w = min(1.0, w + inc)
        else:
            if w > 0:
                dr = self.base_drying_rate
                # Wind
                ws = state.wind_speed_mps if state.wind_speed_mps is not None else 0
                dr *= (1 + ws * self.wind_drying_factor)
                # Track temp
                tt = state.track_temperature_c if state.track_temperature_c is not None else state.air_temperature_c or 25  # noqa: E501
                if tt is not None and tt > 20:
                    dr *= (1 + (tt - 20) * self.temp_drying_factor)
                # Humidity penalty (high humidity slows drying)
                hum = state.humidity_pct if state.humidity_pct is not None else 60
                if hum is not None and hum > 60:
                    dr *= max(0.5, 1 - (hum - 60) * self.humidity_drying_penalty)
                # Traffic disperses water (racing line effect avg)
                traffic = min(1.5, cars_on_track / 20)
                dr *= traffic
                w = max(0.0, w - dr)
        return max(0.0, min(1.0, w))


class TrackEnvironment(BaseModel):
    """Time-varying environment shared across drivers (race-level).

    Holds current WeatherState + derived wetness + regime.
    """

    current_weather: WeatherState
    wetness: float = Field(default=0.0, ge=0, le=1)
    lap: int = 0

    model_config = {"arbitrary_types_allowed": True}

    def grip_factor(self) -> float:
        return self.current_weather.get_grip_multiplier()

    def to_dict(self) -> dict:
        return {
            "lap": self.lap,
            "wetness": self.wetness,
            "weather": self.current_weather.model_dump(),
            "grip": self.grip_factor(),
        }
