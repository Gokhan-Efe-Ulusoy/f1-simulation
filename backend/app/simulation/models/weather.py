from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WeatherCondition(str, Enum):
    """Weather conditions."""

    DRY = "dry"
    OVERCAST = "overcast"
    DAMP = "damp"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    WET = "wet"  # Track wet but not raining
    DRYING = "drying"  # Track drying after rain


class WeatherTrend(str, Enum):
    """Weather trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


class WeatherState(BaseModel):
    """Current weather state."""

    condition: WeatherCondition = WeatherCondition.DRY
    air_temperature: float = Field(default=25.0, ge=-10, le=50)
    track_temperature: float = Field(default=35.0, ge=-5, le=65)
    humidity: float = Field(default=60.0, ge=0, le=100)
    wind_speed: float = Field(default=5.0, ge=0, le=30)  # m/s
    wind_direction: float = Field(default=0.0, ge=0, le=360)  # degrees
    track_wetness: float = Field(default=0.0, ge=0, le=1)  # 0 = dry, 1 = soaking
    precipitation_rate: float = Field(default=0.0, ge=0, le=50)  # mm/hr
    visibility: float = Field(default=1.0, ge=0, le=1)  # 1 = perfect
    pressure_hpa: float = Field(default=1013.0, ge=950, le=1050)

    # Trend
    trend: WeatherTrend = WeatherTrend.STABLE
    trend_strength: float = Field(default=0.0, ge=0, le=1)

    model_config = {"use_enum_values": True}

    def get_grip_multiplier(self) -> float:
        """Get track grip multiplier based on wetness."""
        if self.track_wetness <= 0.05:
            return 1.0
        elif self.track_wetness <= 0.2:
            return 0.95 - self.track_wetness * 0.2  # 0.95 to 0.91
        elif self.track_wetness <= 0.5:
            return 0.91 - (self.track_wetness - 0.2) * 0.4  # 0.91 to 0.79
        elif self.track_wetness <= 0.8:
            return 0.79 - (self.track_wetness - 0.5) * 0.5  # 0.79 to 0.64
        else:
            return max(0.4, 0.64 - (self.track_wetness - 0.8) * 1.2)

    def get_visibility_factor(self) -> float:
        """Get visibility factor (affects driver confidence/mistakes)."""
        if self.condition in (WeatherCondition.HEAVY_RAIN,):
            return 0.7
        elif self.condition in (WeatherCondition.LIGHT_RAIN,):
            return 0.85
        elif self.condition in (WeatherCondition.DAMP, WeatherCondition.WET):
            return 0.95
        return 1.0

    def get_cooling_factor(self) -> float:
        """Get cooling factor for brakes/engine/tires."""
        # Lower track temp = better cooling
        base = 1.0
        if self.track_temperature < 20:
            base = 1.1
        elif self.track_temperature > 50:
            base = 0.9
        # Wet track improves cooling
        if self.track_wetness > 0.3:
            base *= 1.05
        return base

    def is_rain(self) -> bool:
        return self.condition in (WeatherCondition.LIGHT_RAIN, WeatherCondition.HEAVY_RAIN)

    def is_wet_track(self) -> bool:
        return self.track_wetness > 0.2

    def get_appropriate_compounds(self) -> list[str]:
        """Get list of appropriate tyre compounds."""
        if self.condition == WeatherCondition.DRY and self.track_wetness < 0.1:
            return ["soft", "medium", "hard"]
        elif self.condition == WeatherCondition.OVERCAST and self.track_wetness < 0.1:
            return ["soft", "medium", "hard"]
        elif self.condition in (WeatherCondition.DAMP, WeatherCondition.DRYING) or self.track_wetness < 0.3:  # noqa: E501
            return ["intermediate", "medium", "soft"]
        elif self.condition in (WeatherCondition.LIGHT_RAIN,) or self.track_wetness < 0.6:
            return ["intermediate", "wet"]
        else:
            return ["wet", "intermediate"]


class WeatherForecast(BaseModel):
    """Weather forecast for a session."""

    # Per-lap forecasts
    lap_forecasts: list[WeatherState] = Field(default_factory=list)

    # Summary
    rain_probability: float = Field(default=0.1, ge=0, le=1)
    max_precipitation: float = Field(default=0.0, ge=0)
    temperature_range: tuple[float, float] = (20.0, 30.0)

    model_config = {"use_enum_values": True}

    def get_forecast_for_lap(self, lap: int) -> WeatherState:
        if lap < len(self.lap_forecasts):
            return self.lap_forecasts[lap]
        # Extrapolate last known
        return self.lap_forecasts[-1] if self.lap_forecasts else WeatherState()


class WeatherModel(BaseModel):
    """Weather evolution model for a session.
    
    Weather evolves statefully rather than being independently
    randomized every lap.
    """

    # Initial state
    initial_state: WeatherState

    # Evolution parameters
    volatility: float = Field(default=0.1, ge=0, le=1)  # How much weather can change
    persistence: float = Field(default=0.85, ge=0, le=1)  # How much state persists
    rain_threshold: float = Field(default=0.3, ge=0, le=1)  # Wetness needed for rain
    drying_rate: float = Field(default=0.02, ge=0.005, le=0.1)  # Track drying per lap

    # Track-specific
    track_drainage: float = Field(default=0.5, ge=0, le=1)  # How fast track drains
    cloud_cover_base: float = Field(default=0.5, ge=0, le=1)

    # Random provider
    _rng: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def initialize(self, rng: Any) -> None:
        self._rng = rng

    def step(self, current_state: WeatherState, lap: int) -> WeatherState:
        """Evolve weather by one lap."""
        if self._rng is None:
            raise RuntimeError("WeatherModel not initialized with RNG")

        new_state = current_state.model_copy()

        # Temperature evolution
        temp_drift = self._rng.normal(0, 0.2)  # Small random drift
        new_state.air_temperature += temp_drift * self.volatility

        # Track temp follows air temp with lag
        track_temp_target = new_state.air_temperature + 10  # Track typically 10C hotter
        new_state.track_temperature += (track_temp_target - new_state.track_temperature) * 0.1
        new_state.track_temperature += self._rng.normal(0, 0.15) * self.volatility

        # Humidity
        humidity_drift = self._rng.normal(0, 1.0) * self.volatility
        new_state.humidity = max(0, min(100, new_state.humidity + humidity_drift))

        # Wind
        wind_drift = self._rng.normal(0, 0.5) * self.volatility
        new_state.wind_speed = max(0, new_state.wind_speed + wind_drift)
        new_state.wind_direction = (new_state.wind_direction + self._rng.normal(0, 10)) % 360

        # Precipitation and wetness evolution
        if current_state.is_rain():
            # Raining - wetness increases
            precip = current_state.precipitation_rate
            new_state.track_wetness = min(1.0, new_state.track_wetness + precip * 0.01)
            # Precipitation can change
            precip_change = self._rng.normal(0, precip * 0.2)
            new_state.precipitation_rate = max(0, precip + precip_change)
        else:
            # Not raining - track dries
            if new_state.track_wetness > 0:
                dry_rate = self.drying_rate * (1 + new_state.wind_speed * 0.02)
                dry_rate *= self.track_drainage
                # Sun/temp accelerates drying
                if new_state.track_temperature > 25:
                    dry_rate *= 1.2
                new_state.track_wetness = max(0, new_state.track_wetness - dry_rate)

        # Chance of rain starting/stopping
        rain_roll = self._rng.random()

        if not current_state.is_rain():
            # Check if rain starts
            rain_prob = self._calculate_rain_probability(new_state)
            if rain_roll < rain_prob * self.volatility:
                new_state = self._start_rain(new_state)
        else:
            # Check if rain stops
            stop_prob = 0.05 * (1 - new_state.precipitation_rate / 20)
            if rain_roll < stop_prob:
                new_state = self._stop_rain(new_state)

        # Update condition based on wetness and precipitation
        new_state.condition = self._determine_condition(new_state)

        # Update visibility
        new_state.visibility = self._calculate_visibility(new_state)

        # Update trend
        new_state.trend = self._determine_trend(current_state, new_state)

        return new_state

    def _calculate_rain_probability(self, state: WeatherState) -> float:
        """Calculate probability of rain starting this lap."""
        base = 0.01
        # Higher humidity = more likely
        base += (state.humidity / 100) * 0.05
        # Lower pressure = more likely
        if state.pressure_hpa < 1000:
            base += (1000 - state.pressure_hpa) * 0.0002
        # Cloud cover
        base += self.cloud_cover_base * 0.02
        return min(0.15, base)

    def _start_rain(self, state: WeatherState) -> WeatherState:
        """Transition to rain."""
        state.condition = WeatherCondition.LIGHT_RAIN
        state.precipitation_rate = self._rng.uniform(0.5, 3.0)
        state.trend = WeatherTrend.WORSENING
        state.trend_strength = self._rng.uniform(0.3, 0.7)
        return state

    def _stop_rain(self, state: WeatherState) -> WeatherState:
        """Transition from rain."""
        if state.track_wetness > 0.5:
            state.condition = WeatherCondition.WET
        elif state.track_wetness > 0.2:
            state.condition = WeatherCondition.DAMP
        else:
            state.condition = WeatherCondition.DRYING
        state.precipitation_rate = 0.0
        state.trend = WeatherTrend.IMPROVING
        state.trend_strength = self._rng.uniform(0.3, 0.7)
        return state

    def _determine_condition(self, state: WeatherState) -> WeatherCondition:
        """Determine condition from state variables."""
        if state.precipitation_rate > 5:
            return WeatherCondition.HEAVY_RAIN
        elif state.precipitation_rate > 0:
            return WeatherCondition.LIGHT_RAIN
        elif state.track_wetness > 0.5:
            return WeatherCondition.WET
        elif state.track_wetness > 0.1:
            return WeatherCondition.DAMP
        elif state.humidity > 90:
            return WeatherCondition.OVERCAST
        return WeatherCondition.DRY

    def _calculate_visibility(self, state: WeatherState) -> float:
        """Calculate visibility from state."""
        vis = 1.0
        if state.condition == WeatherCondition.HEAVY_RAIN:
            vis = 0.6
        elif state.condition == WeatherCondition.LIGHT_RAIN:
            vis = 0.8
        elif state.condition == WeatherCondition.WET:
            vis = 0.85
        elif state.condition == WeatherCondition.DAMP:
            vis = 0.95
        # Spray effect from other cars (not modeled here, applied in race)
        return vis

    def _determine_trend(self, old: WeatherState, new: WeatherState) -> WeatherTrend:
        """Determine weather trend."""
        if new.precipitation_rate > old.precipitation_rate + 0.5:
            return WeatherTrend.WORSENING
        elif new.precipitation_rate < old.precipitation_rate - 0.5:
            return WeatherTrend.IMPROVING
        elif new.track_wetness > old.track_wetness + 0.05:
            return WeatherTrend.WORSENING
        elif new.track_wetness < old.track_wetness - 0.05:
            return WeatherTrend.IMPROVING
        return WeatherTrend.STABLE

    def generate_forecast(self, total_laps: int) -> WeatherForecast:
        """Generate a forecast for the entire session."""
        if self._rng is None:
            raise RuntimeError("WeatherModel not initialized with RNG")

        forecasts = []
        state = self.initial_state

        for lap in range(total_laps):
            forecasts.append(state.model_copy())
            state = self.step(state, lap)

        max_precip = max(f.precipitation_rate for f in forecasts)
        min_temp = min(f.air_temperature for f in forecasts)
        max_temp = max(f.air_temperature for f in forecasts)

        return WeatherForecast(
            lap_forecasts=forecasts,
            rain_probability=1.0 if max_precip > 0 else 0.0,
            max_precipitation=max_precip,
            temperature_range=(min_temp, max_temp),
        )


def create_weather_model(
    condition: WeatherCondition = WeatherCondition.DRY,
    air_temp: float = 25.0,
    track_temp: float = 35.0,
    humidity: float = 60.0,
    volatility: float = 0.1,
    seed: int | None = None,
) -> tuple[WeatherModel, Any]:
    """Create a weather model with initial state."""
    import numpy as np
    rng = np.random.default_rng(seed)

    initial = WeatherState(
        condition=condition,
        air_temperature=air_temp,
        track_temperature=track_temp,
        humidity=humidity,
        track_wetness=0.8 if condition in (WeatherCondition.WET, WeatherCondition.HEAVY_RAIN) else
                        0.4 if condition in (WeatherCondition.DAMP, WeatherCondition.LIGHT_RAIN) else 0.0,  # noqa: E501
        precipitation_rate=5.0 if condition == WeatherCondition.HEAVY_RAIN else
                          1.5 if condition == WeatherCondition.LIGHT_RAIN else 0.0,
    )

    model = WeatherModel(
        initial_state=initial,
        volatility=volatility,
    )
    model.initialize(rng)

    return model, rng
