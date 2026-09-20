"""Phase 29 — Unified execution orchestration (one execution path)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.services.hashing import request_hash
from app.simulation.version import MODEL_VERSION, RACEENGINE_VERSION


@dataclass
class SimulationRequest:
    race_id: str
    seed: int | None = 42
    laps: int | None = None
    modifiers: dict[str, Any] | None = None
    simulation_type: str = "race"  # race, monte_carlo, scenario, strategy, replay


@dataclass
class MonteCarloRequest:
    race_id: str
    seed: int | None = 42
    simulations: int = 1000
    laps: int | None = None
    modifiers: dict[str, Any] | None = None


MODIFIER_SUPPORT: dict[str, dict[str, str]] = {
    "baseline": {"status": "supported", "tier": "CALIBRATED", "note": "default production path"},
    "weather": {"status": "provenance_only_single_provenance_only", "tier": "PRIOR_ONLY", "note": "vectorized MC honours via hypothetical_modifiers weather.enabled; single-race remains PROVENANCE_ONLY (no validated physical effect in RaceEngine)"},  # noqa: E501
    "setup": {"status": "provenance_only_single", "tier": "PRIOR_ONLY", "note": "vectorized MC honours via setup_offsets_for_scenario; single-race PROVENANCE_ONLY"},  # noqa: E501
    "tyre": {"status": "supported_conditional", "tier": "PRIOR_ONLY", "note": "vectorized supports for 2023+ PIRELLI era via tyre kernels; single-race uses TyreModel but historical stint not validated"},  # noqa: E501
    "race_control": {"status": "supported", "tier": "PRIOR_ONLY", "note": "both paths support race_control_enabled via engine policy (vectorized via trajectories, single via RaceControlEngine)"},  # noqa: E501
    "scenario": {"status": "supported", "tier": "PRIOR_ONLY", "note": "via allowlist registry, ScenarioEngine + ReplayEngine"},  # noqa: E501
    "strategy": {"status": "supported", "tier": "PRIOR_ONLY", "note": "via DecisionEngine, prior only"},  # noqa: E501
    "fuel": {"status": "unsupported", "tier": "NON_IDENTIFIABLE", "note": "fuel proxy only, no telemetry"},  # noqa: E501
}


def describe_modifiers(modifiers: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    """Return support map for requested modifiers, never upgrading tiers."""
    if not modifiers:
        return {"baseline": MODIFIER_SUPPORT["baseline"]}
    out: dict[str, dict[str, str]] = {}
    for k in modifiers.keys():
        out[k] = MODIFIER_SUPPORT.get(k, {"status": "unsupported", "tier": "NON_IDENTIFIABLE", "note": "unknown modifier"})  # noqa: E501
    return out


def build_request_hash_for_race(race_id: str, seed: int | None, laps: int | None, modifiers: dict[str, Any] | None) -> str:  # noqa: E501
    return request_hash(
        race_id=race_id,
        simulation_type="race",
        seed=seed,
        laps=laps,
        modifiers=modifiers or {},
        engine_version=RACEENGINE_VERSION,
        model_version=MODEL_VERSION,
        dataset_version="f1-dataset-v1.3",
    )


def build_request_hash_for_montecarlo(race_id: str, seed: int | None, simulations: int, laps: int | None, modifiers: dict[str, Any] | None) -> str:  # noqa: E501
    return request_hash(
        race_id=race_id,
        simulation_type="monte_carlo",
        seed=seed,
        sample_count=simulations,
        laps=laps,
        modifiers=modifiers or {},
        engine_version=RACEENGINE_VERSION,
        model_version=MODEL_VERSION,
        dataset_version="f1-dataset-v1.3",
    )


# Unified service functions that delegate to existing engines

def execute_single_race(race_id: str, seed: int | None, laps_override: int | None, modifiers: dict[str, Any] | None = None, track_id: str | None = None) -> dict[str, Any]:  # noqa: E501
    """One execution path for single race: delegates to simulation_service."""
    from app.services.simulation_service import simulate_single_race as _sim

    # Unify modifiers: currently single-race only honours race_control/strategy via SimulationConfig.
    # Weather/setup remain provenance-only by design (see MODIFIER_SUPPORT).
    enable_strategy = bool((modifiers or {}).get("strategy", False)) if modifiers else False
    enable_race_control = bool((modifiers or {}).get("race_control", False)) if modifiers else False
    # If generic enable_strategy flag passed via direct args, respect it
    # For backward compat, also check modifiers dict
    # Note: weather/setup requested -> recorded as unsupported/provenance_only, not applied
    enable_strategy = enable_strategy or bool((modifiers or {}).get("enable_strategy", False))
    enable_race_control = enable_race_control or bool((modifiers or {}).get("enable_race_control", False))  # noqa: E501
    # For API backward compat, if modifiers contains enable_weather/setup, note but do not apply
    t0 = time.perf_counter()
    result = _sim(
        race_id=race_id,
        seed=seed,
        laps_override=laps_override,
        enable_strategy=enable_strategy,
        enable_setup=bool((modifiers or {}).get("setup", False)) or bool((modifiers or {}).get("enable_setup", False)),  # noqa: E501
        enable_weather=bool((modifiers or {}).get("weather", True)) if modifiers and "weather" in modifiers else True,  # noqa: E501
        enable_race_control=enable_race_control,
        track_id=track_id,
    )
    elapsed = time.perf_counter() - t0
    result["execution_metadata"] = {
        "request_hash": build_request_hash_for_race(race_id, seed, laps_override, modifiers),
        "execution_time": elapsed,
        "modifiers_support": describe_modifiers(modifiers),
    }
    return result


def execute_monte_carlo(race_id: str, seed: int | None, simulations: int, laps_override: int | None, modifiers: dict[str, Any] | None = None, chunk_size: int | None = None, progress_callback: Any = None, cancel_check: Any = None) -> dict[str, Any]:  # noqa: E501
    """One execution path for Monte Carlo: delegates to montecarlo_service (chunked optional)."""
    from app.services.montecarlo_service import run_montecarlo as _mc

    enable_weather = True
    enable_race_control = True
    enable_setup = False
    enable_strategy = False
    if modifiers:
        if "weather" in modifiers:
            w = modifiers["weather"]
            if isinstance(w, dict) and w.get("enabled") is False:
                enable_weather = False
            elif w is False:
                enable_weather = False
        if "race_control" in modifiers:
            rc = modifiers["race_control"]
            if isinstance(rc, dict) and rc.get("enabled") is False:
                enable_race_control = False
            elif rc is False:
                enable_race_control = False
        if "setup" in modifiers:
            enable_setup = True
        if "strategy" in modifiers:
            enable_strategy = True

    t0 = time.perf_counter()
    result = _mc(
        race_id=race_id,
        simulations=simulations,
        seed=seed,
        enable_strategy=enable_strategy,
        enable_setup=enable_setup,
        enable_weather=enable_weather,
        enable_race_control=enable_race_control,
        laps_override=laps_override,
        chunk_size=chunk_size,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    elapsed = time.perf_counter() - t0
    result["execution_metadata"] = {
        "request_hash": build_request_hash_for_montecarlo(race_id, seed, simulations, laps_override, modifiers),  # noqa: E501
        "execution_time": elapsed,
        "modifiers_support": describe_modifiers(modifiers),
    }
    return result
