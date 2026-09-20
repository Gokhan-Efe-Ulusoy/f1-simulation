"""Phase 22 — Historical observation contract.

Builds the information set available at lap `t` (t=0 is pre-race). Anything
that could only be known from the future — final result, future pits,
realized weather, future race-control events, future telemetry — is excluded
by construction (None + NON_IDENTIFIABLE, never a fabricated substitute).
"""
from __future__ import annotations

from typing import Any

from app.simulation.replay.models import HistoricalObservationState, HistoricalRace, ObservedValue


def _obs(
    value: Any, source: str, tier: str, hrace: HistoricalRace,
    obs_ts: str = "",
) -> ObservedValue:
    return ObservedValue(
        value=value,
        source=source,
        evidence_tier=tier,
        observation_timestamp=obs_ts or hrace.race_date,
        as_of=hrace.as_of,
    )


def build_observation(hrace: HistoricalRace, lap: int = 0) -> HistoricalObservationState:
    """Observation state at lap `lap` (0 = pre-race).

    Lap-by-lap canonical data (pit timing, incidents, telemetry, weather)
    does not exist at the required granularity, so every in-race history
    field is None + NON_IDENTIFIABLE for lap > 0 rather than an invented
    reconstruction. Pre-race pace estimates come from the leakage-safe
    calibration API (as_of-gated) where available.
    """
    lap = max(0, int(lap))
    state = HistoricalObservationState(
        race_id=hrace.race_id,
        season=hrace.season_id,
        round=hrace.round,
        circuit_id=hrace.circuit_id,
        lap=lap,
        race_date=hrace.race_date,
        as_of=hrace.as_of,
    )
    if hrace.grid_order:
        state.grid_order = _obs(
            list(hrace.grid_order), "canonical:results.grid_position",
            "LIMITED", hrace,
        )
    if hrace.drivers:
        state.drivers = _obs(
            [d["driver_id"] for d in hrace.drivers],
            "canonical:results.driver_id", "LIMITED", hrace,
        )
    # No historical weather observations in the canonical dataset.
    state.weather_current = _obs(
        None, "unavailable:no_historical_weather", "NON_IDENTIFIABLE", hrace,
    )
    state.weather_forecast_summary = _obs(
        None, "model_prior:WeatherEngine(as_of)", "PRIOR_ONLY", hrace,
    )
    # Pre-race: the model prior assumes GREEN; nothing observed.
    state.race_control_phase = _obs(
        "GREEN" if lap == 0 else None,
        "model_prior:RaceControlEngine" if lap == 0 else "unavailable:no_lap_rc_data",
        "PRIOR_ONLY" if lap == 0 else "NON_IDENTIFIABLE",
        hrace,
    )
    state.sector_flags = _obs(
        None, "unavailable:no_sector_data", "NON_IDENTIFIABLE", hrace,
    )
    # Tyre: starting compounds are not identified historically.
    state.tyre_state = _obs(
        None, "unavailable:no_historical_compounds", "NON_IDENTIFIABLE", hrace,
    )
    state.tyre_age = _obs(
        0 if lap == 0 else None,
        "model_default:age_0_at_start" if lap == 0 else "unavailable:no_lap_tyre_data",
        "PRIOR_ONLY" if lap == 0 else "NON_IDENTIFIABLE",
        hrace,
    )
    state.fuel_state = _obs(
        None, "unavailable:no_fuel_data", "NON_IDENTIFIABLE", hrace,
    )
    # Leakage-safe pre-race pace estimates (strict_before as_of).
    try:
        from app.data.calibration_api import (
            get_driver_performance, get_constructor_performance,
        )

        dpace = {}
        for d in hrace.drivers:
            perf = get_driver_performance(d["driver_id"], hrace.as_of)
            if perf.get("value") is not None:
                dpace[d["driver_id"]] = perf["value"]
        if dpace:
            state.driver_pace_estimate = _obs(
                dpace, "calibration_api:driver_pace(as_of)", "LIMITED", hrace,
            )
        cpace = {}
        for cid in {d.get("constructor_id", "") for d in hrace.drivers if d.get("constructor_id")}:
            perf = get_constructor_performance(cid, hrace.as_of)
            if perf.get("value") is not None:
                cpace[cid] = perf["value"]
        if cpace:
            state.constructor_pace_estimate = _obs(
                cpace, "calibration_api:constructor_pace(as_of)", "LIMITED", hrace,
            )
    except Exception:
        pass
    # In-race histories: no lap-granular canonical source -> not identified.
    state.pit_history_observed_until_t = _obs(
        [] if lap == 0 else None,
        "unavailable:no_lap_pit_data", "NON_IDENTIFIABLE", hrace,
    )
    state.incident_history_observed_until_t = _obs(
        [] if lap == 0 else None,
        "unavailable:no_lap_incident_data", "NON_IDENTIFIABLE", hrace,
    )
    state.strategy_state = _obs(
        None, "unavailable:no_historical_strategy", "NON_IDENTIFIABLE", hrace,
    )
    state.setup_state = _obs(
        None, "unavailable:no_historical_setups_neutral_baseline",
        "NON_IDENTIFIABLE", hrace,
    )
    state.realized_result_excluded = True
    return state


def assert_no_future_fields(state: HistoricalObservationState) -> list[str]:
    """Leakage guard: fail if any forbidden realized-future content appears."""
    violations: list[str] = []
    dump = state.model_dump()
    dump.pop("realized_result_excluded", None)  # the guard itself, not content
    import json as _json

    blob = _json.dumps(dump, default=str).lower()
    for token in (
        "final_position", "future_", "realized", "winner", "podium_result",
        "finishing_position", "championship", "standing",
    ):
        if token in blob:
            violations.append(f"observation carries forbidden token {token!r}")
    if state.realized_result_excluded is not True:
        violations.append("realized_result_excluded guard disabled")
    return violations
