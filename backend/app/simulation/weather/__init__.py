"""Weather & Environmental State Engine v1 (Phase 17).

Modular chain:
  WeatherState(t) -> TrackEnvironment(t) -> TyreEnvironment(t) -> Grip(t) -> LapTime(t) -> Incident(t)  # noqa: E501

Exposes canonical state, regimes, environment, transitions, calibration, forecast.
"""
from app.simulation.weather.state import WeatherState, WeatherEvidence, RainfallIntensity, EvidenceTier  # noqa: E501
from app.simulation.weather.regime import WeatherRegime
from app.simulation.weather.environment import TrackEnvironment, WetnessModel
from app.simulation.weather.transition import WeatherTransitionModel
from app.simulation.weather.forecast import WeatherForecast
from app.simulation.weather.calibration import load_weather_observations, calibrate_weather

__all__ = [
    "WeatherState",
    "WeatherEvidence",
    "RainfallIntensity",
    "EvidenceTier",
    "WeatherRegime",
    "TrackEnvironment",
    "WetnessModel",
    "WeatherTransitionModel",
    "WeatherForecast",
    "load_weather_observations",
    "calibrate_weather",
]

__version__ = "weather-v1.0.0"
CALIBRATION_VERSION = "weather-calibration-v1.0.0"
