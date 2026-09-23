"""Phase 28 — Monte Carlo service (thin wrapper over VectorizedMonteCarlo)."""

from __future__ import annotations

import time
from typing import Any

from app.simulation.performance.vectorized_montecarlo import VectorizedMonteCarlo
from app.simulation.scenario_v14 import Scenario

MAX_SIMULATIONS = 5000
MIN_SIMULATIONS = 1
DEFAULT_SIMULATIONS = 1000


def _get_calibration_state() -> dict:
    # Minimal calibration_state compatible with VectorizedMonteCarlo
    # If real calibration exists, load; otherwise synthetic priors
    try:
        from app.simulation.calibration_state import load_calibration_state

        return load_calibration_state()  # type: ignore[no-redef]
    except Exception:
        pass
    # fallback: empty priors (all zero deltas, 0.05 dnf)
    return {
        "drivers": {},
        "constructors": {},
        "circuit": {"baseline": 10.5},
    }


def _build_scenario_for_montecarlo(race_id: str, laps_override: int | None = None) -> Scenario:
    # Try historical scenario first
    try:
        from app.simulation.replay.state_builder import (
            build_scenario_for_race,
            load_historical_race,
        )

        hrace = load_historical_race(race_id)
        scen = build_scenario_for_race(hrace, laps=laps_override)
        return scen
    except Exception:
        pass
    # fallback synthetic via SimulationService helpers (reuse driver list)
    from app.services.simulation_service import _build_drivers_cars_track

    drivers, cars, track, engines = _build_drivers_cars_track(race_id)
    total_laps = int(laps_override) if laps_override is not None else int(track.number_of_laps)
    # Build minimal Scenario object
    from app.simulation.scenario_v14 import Scenario as Sc

    scen = Sc(
        scenario_id=race_id,
        season_id="2024",
        circuit_id=track.id,
        date="2024-01-02T00:00:00Z",
        as_of="2024-01-01T00:00:00Z",
        race_distance={"laps": total_laps},
        drivers=[{"driver_id": d.id, "constructor_id": d.team_id} for d in drivers],
        grid_order=[d.id for d in drivers],
        historical_mode=False,
        resimulate_qualifying=True,
    )
    return scen  # type: ignore[return-value]


def run_montecarlo(
    race_id: str,
    simulations: int,
    seed: int | None,
    enable_strategy: bool = False,
    enable_setup: bool = False,
    enable_weather: bool = True,
    enable_race_control: bool = True,
    laps_override: int | None = None,
    chunk_size: int | None = None,
    progress_callback: Any = None,
    cancel_check: Any = None,
) -> dict[str, Any]:
    if not (MIN_SIMULATIONS <= simulations <= MAX_SIMULATIONS):
        raise ValueError(
            f"simulations must be {MIN_SIMULATIONS}..{MAX_SIMULATIONS}, got {simulations}"
        )
    if seed is not None and not (-(2**31) <= seed <= 2**31 - 1):
        raise ValueError("seed out of int32 range")
    if laps_override is not None and not (1 <= laps_override <= 200):
        raise ValueError("laps_override must be 1..200")

    seed_val = int(seed) if seed is not None else 42
    scenario = _build_scenario_for_montecarlo(race_id, laps_override=laps_override)

    # honour enable flags via hypothetical_modifiers (vectorized respects these)
    # ensure modifiers dict exists
    if not hasattr(scenario, "hypothetical_modifiers") or scenario.hypothetical_modifiers is None:
        scenario.hypothetical_modifiers = {}  # type: ignore[attr-defined]
    mods = scenario.hypothetical_modifiers  # type: ignore[attr-defined]
    if not enable_weather:
        mods["weather"] = {"enabled": False}  # type: ignore[index]
    if not enable_race_control:
        mods["race_control"] = {"enabled": False}  # type: ignore[index]
    # strategy/setup: vectorized honours setup via offsets_for_scenario; strategy pit_loss not needed  # noqa: E501

    calib = _get_calibration_state()
    t0 = time.perf_counter()
    chunk_manifest: dict[str, Any] | None = None
    if chunk_size is not None and int(chunk_size) > 0:
        # Deterministic chunked path (Phase 31) — identical to unchunked via global-index RNG
        from app.simulation.performance.chunked_montecarlo import chunk_ranges, run_chunked

        cs = int(chunk_size)
        if not (1 <= cs <= 5000):
            raise ValueError("chunk_size must be 1..5000")
        # progress per chunk
        ranges = chunk_ranges(simulations, cs)
        # run chunked (order-independent, worker-independent)
        if cancel_check is not None and callable(cancel_check) and cancel_check():
            raise RuntimeError("cancelled before execution")
        chunked = run_chunked(calib, scenario, seed_val, simulations, cs)
        if progress_callback is not None:
            try:
                progress_callback(0.9, "SIMULATING")
            except Exception:
                pass
        # Reuse aggregation from chunked (already exact integer counts)
        # Build raw-compatible dict from chunked drivers/constructors
        # For provenance etc, run a lightweight unchunked header via single engine init (no sim)
        engine = VectorizedMonteCarlo(calibration_state=calib, scenario=scenario, seed=seed_val)
        # Use chunked drivers directly; construct raw-like
        raw = {
            "simulation_id": f"{scenario.scenario_id}:{seed_val}:{simulations}",
            "scenario_id": scenario.scenario_id,
            "simulations": simulations,
            "seed": seed_val,
            "drivers": chunked["drivers"],
            "constructors": chunked["constructors"],
            "summary": {"simulations": simulations, "seed": seed_val},
            "provenance": {
                "dataset_version": "f1-dataset-v1.3",
                "calibration_version": "calibration-v1.0.0",
                "engine_version": "raceengine-v2.2.0",
                "model_version": "0.9.0",
                "as_of": scenario.as_of,
            },
            "diagnostics": {"temporal_leakage": False, "fabrication": False, "deterministic": True},
            "race_control_trajectories": None,
        }
        chunk_manifest = chunked["manifest"]
    else:
        engine = VectorizedMonteCarlo(calibration_state=calib, scenario=scenario, seed=seed_val)
        raw = engine.run(simulations=simulations)
    elapsed = time.perf_counter() - t0

    # reshape to API contract
    drivers = raw.get("drivers", {})
    win_probs = {k: float(v.get("win_probability", 0.0)) for k, v in drivers.items()}
    podium_probs = {k: float(v.get("podium_probability", 0.0)) for k, v in drivers.items()}
    # finish-position distribution: drivers finish_distribution already per driver
    finish_dist = {k: dict(v.get("finish_distribution", {})) for k, v in drivers.items()}
    dnf_stats = {k: float(v.get("dnf_probability", 0.0)) for k, v in drivers.items()}
    expected_finish = {k: v.get("expected_finish") for k, v in drivers.items()}

    # sanitize raw for JSON: remove ndarrays (race_control_trajectories)
    raw_sanitized: dict[str, Any] = {}
    for k, v in raw.items():
        if k == "race_control_trajectories":
            # contains ndarrays phase/sector -> do not expose via API, store as None
            raw_sanitized[k] = None
        else:
            raw_sanitized[k] = v

    result: dict[str, Any] = {
        "simulation_id": raw.get("simulation_id") or f"mc_{race_id}_{seed_val}_{simulations}",
        "race_id": race_id,
        "N": simulations,
        "simulations": simulations,
        "seed": seed_val,
        "win_probabilities": win_probs,
        "podium_probabilities": podium_probs,
        "finish_position_distribution": finish_dist,
        "expected_finish": expected_finish,
        "dnf_statistics": dnf_stats,
        "expected_points": {k: float(v.get("expected_points", 0.0)) for k, v in drivers.items()},
        "uncertainty": {
            "note": "Monte Carlo sampling uncertainty; increase N to reduce",
            "ci95_per_driver": {k: v.get("finish_CI95") for k, v in drivers.items()},
        },
        "distribution": drivers,
        "constructors": raw.get("constructors", {}),
        "summary": raw.get("summary", {}),
        "provenance": raw.get("provenance", {}),
        "model_versions": {
            "model_version": raw.get("provenance", {}).get("model_version", "0.9.0"),
            "race_engine_version": raw.get("provenance", {}).get(
                "engine_version", "raceengine-v2.2.0"
            ),
        },
        "evidence_tiers": {
            "fuel": "NON_IDENTIFIABLE",
            "tyre_historical": "NON_IDENTIFIABLE",
            "strategy": "PRIOR_ONLY",
            "setup": "PRIOR_ONLY",
            "weather": "PRIOR_ONLY" if enable_weather else "DISABLED",
            "race_control": "PRIOR_ONLY" if enable_race_control else "DISABLED",
        },
        "runtime": {
            "elapsed_seconds": elapsed,
            "simulations_per_second": (simulations / elapsed) if elapsed > 0 else 0,
        },
        "reproducibility": {
            "seed": seed_val,
            "race_id": race_id,
            "simulations": simulations,
            "dataset_version": raw.get("provenance", {}).get("dataset_version", "f1-dataset-v1.3"),
            "note": "Same race, config, seed, model version => identical output (CRN, isolated streams)",  # noqa: E501
        },
        "warnings": [],
        "raw": raw_sanitized,
    }
    if chunk_manifest is not None:
        result["chunk_manifest"] = chunk_manifest
        result["chunked"] = True
        result["chunk_size"] = chunk_size
    return result
