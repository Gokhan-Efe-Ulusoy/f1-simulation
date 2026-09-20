"""Validation helpers for weather state."""
from __future__ import annotations

from app.simulation.weather.state import WeatherState


def validate_state(state: WeatherState) -> list[str]:
    errors: list[str] = []
    if state.track_wetness is not None and not (0 <= state.track_wetness <= 1):
        errors.append(f"track_wetness {state.track_wetness} out of [0,1]")
    if state.air_temperature_c is not None and not (-10 <= state.air_temperature_c <= 50):
        errors.append("air_temperature out of range")
    if state.track_temperature_c is not None and not (-5 <= state.track_temperature_c <= 65):
        errors.append("track_temperature out of range")
    if state.humidity_pct is not None and not (0 <= state.humidity_pct <= 100):
        errors.append("humidity out of range")
    if state.pressure_hpa is not None and not (900 <= state.pressure_hpa <= 1100):
        errors.append("pressure out of range")
    if state.wind_speed_mps is not None and not (0 <= state.wind_speed_mps <= 50):
        errors.append("wind_speed out of range")
    if state.rainfall_mm_h is not None and not (0 <= state.rainfall_mm_h <= 100):
        errors.append("rainfall out of range")
    return errors
