"""Phase 28 — Simulation service: single deterministic race (thin wrapper over RaceEngine)."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from app.simulation.core.random import RandomProvider
from app.simulation.core.state import SimulationConfig
from app.simulation.version import MODEL_VERSION, RACEENGINE_VERSION, SIMULATION_VERSION


# deterministic driver/car generation helpers
def _deterministic_skill(driver_id: str, base: int = 75) -> float:
    h = int(hashlib.sha256(driver_id.encode()).hexdigest()[:8], 16)
    # 60-90 range
    return float(60 + (h % 3000) / 100.0)


def _build_drivers_cars_track(race_id: str, track_id_override: str | None = None):
    from app.simulation.models.car import Car, Engine
    from app.simulation.models.driver import Driver
    from app.simulation.models.track import get_2024_calendar

    # resolve track
    track_id = (track_id_override or "").lower() if track_id_override else None
    # try to infer from race_id like "2024-bahrain" -> bahrain
    if not track_id:
        low = race_id.lower()
        for cand in ["bahrain", "saudi_arabia", "australia", "monaco", "spain", "monza"]:
            if cand in low:
                track_id = cand
                break
        if not track_id:
            # try canonical race -> circuit_id
            try:
                from app.services.race_service import get_race

                rec = get_race(race_id)
                if rec and rec.get("circuit_id"):
                    cid = str(rec["circuit_id"]).lower()
                    # map canonical circuit ids to calendar ids where possible
                    mapping = {
                        "bahrain": "bahrain",
                        "jeddah": "saudi_arabia",
                        "albert_park": "australia",
                        "monaco": "monaco",
                        "catalunya": "spain",
                        "monza": "monza",
                    }
                    track_id = mapping.get(cid, cid)
            except Exception:
                pass
    calendar = {t.id: t for t in get_2024_calendar()}
    track = calendar.get(track_id or "bahrain") or calendar["bahrain"]

    # build 20 drivers / cars deterministically from race_id
    drivers: list[Driver] = []
    cars: dict[str, Car] = {}
    engines: dict[str, Engine] = {}
    # 10 teams x2
    team_ids = [f"team_{i:02d}" for i in range(10)]
    driver_ids: list[str] = []
    # if historical race, prefer its driver list
    try:
        from app.simulation.replay.state_builder import load_historical_race

        hrace = load_historical_race(race_id)
        if hrace.drivers:
            for d in hrace.drivers:
                did = str(d.get("driver_id"))
                driver_ids.append(did)
    except Exception:
        pass
    if len(driver_ids) < 10:
        # synthetic 20
        for i in range(20):
            driver_ids.append(f"driver_{i:02d}")

    for idx, did in enumerate(driver_ids[:20]):
        team_id = team_ids[idx // 2]
        skill = _deterministic_skill(did)
        drv = Driver(
            id=did,
            name=f"Driver {did}",
            short_name=did[:3].upper(),
            number=(idx + 1) % 99,
            nationality="Unknown",
            date_of_birth="1995-01-01",
            team_id=team_id,
            overall_skill=skill,
            qualifying_skill=skill + 1,
            race_skill=skill,
            consistency=75,
            aggression=50,
            tyre_management=75,
            wet_weather_skill=75,
            overtaking=75,
            defending=75,
            start_performance=75,
        )
        drivers.append(drv)
        engine_id = f"engine_{team_id}"
        if engine_id not in engines:
            engines[engine_id] = Engine(
                id=engine_id,
                name=f"Engine {team_id}",
                manufacturer="Generic",
                supplier_id=team_id,
            )
        car = Car(
            id=f"car_{did}",
            name=f"Car {did}",
            team_id=team_id,
            engine_id=engine_id,
            year=2024,
            overall_downforce=75,
            aero_efficiency=75,
        )
        cars[did] = car

    return drivers, cars, track, engines


def _provenance(seed: int | None, race_id: str, config: SimulationConfig) -> dict[str, Any]:
    return {
        "dataset_version": "f1-dataset-v1.3",
        "calibration_version": "calibration-v1.0.0",
        "model_version": MODEL_VERSION,
        "race_engine_version": RACEENGINE_VERSION,
        "simulation_version": SIMULATION_VERSION,
        "race_id": race_id,
        "seed": seed,
        "config_version": "1.0.0",
        "enable_strategy": bool(config.strategy_enabled),
        "enable_setup": bool(
            getattr(config, "setup_enabled", False) if hasattr(config, "setup_enabled") else False
        ),
        "enable_weather": bool(
            getattr(config, "weather_enabled", True) if hasattr(config, "weather_enabled") else True
        ),
        "enable_race_control": bool(config.race_control_enabled),
        "evidence_tiers": {
            "fuel": "NON_IDENTIFIABLE",
            "tyre_historical": "NON_IDENTIFIABLE",
            "strategy": "PRIOR_ONLY",
            "setup": "PRIOR_ONLY",
            "weather_historical": "PRIOR_ONLY",
            "race_control_historical": "PRIOR_ONLY",
            "driver": "LIMITED",
            "circuit": "LIMITED",
        },
    }


def simulate_single_race(
    race_id: str,
    seed: int | None,
    laps_override: int | None = None,
    enable_strategy: bool = False,
    enable_setup: bool = False,
    enable_weather: bool = True,
    enable_race_control: bool = False,
    track_id: str | None = None,
) -> dict[str, Any]:
    from app.simulation.core.race_engine import RaceEngine

    if seed is not None and not (-(2**31) <= seed <= 2**31 - 1):
        raise ValueError("seed out of int32 range")
    if laps_override is not None and not (1 <= laps_override <= 200):
        raise ValueError("laps_override must be 1..200")

    drivers, cars, track, engines = _build_drivers_cars_track(race_id, track_id_override=track_id)
    total_laps = int(laps_override) if laps_override is not None else int(track.number_of_laps)

    config = SimulationConfig(
        simulation_id=f"race_{race_id}_{seed}",
        seed=seed,
        track_id=track.id,
        total_laps=total_laps,
        strategy_enabled=bool(enable_strategy),
        race_control_enabled=bool(enable_race_control),
    )
    # Weather toggle not in SimulationConfig; default enabled
    # Setup toggle: provenance only (single-race PRIOR_ONLY)
    rng = RandomProvider(seed=seed if seed is not None else 42)
    engine = RaceEngine()
    t0 = time.perf_counter()
    result = engine.simulate_race(
        config=config, drivers=drivers, cars=cars, track=track, rng=rng, engines=engines
    )
    elapsed = time.perf_counter() - t0

    # Normalize RaceResult to API shape
    # result is RaceResult (pydantic)
    rd = result.model_dump() if hasattr(result, "model_dump") else dict(result)  # type: ignore[attr-defined]  # noqa: E501
    classification = [
        {
            "position": r.get("position"),
            "driver_id": r.get("driver_id"),
            "total_time": r.get("total_time"),
            "status": r.get("status"),
            "laps_completed": r.get("laps_completed"),
            "best_lap_time": r.get("best_lap_time"),
            "points": r.get("points"),
        }
        for r in (rd.get("results") or [])
    ]
    # lap summary: if events contain lap times, aggregate
    lap_summary = {
        "total_laps": rd.get("total_laps") or total_laps,
        "completed_laps": rd.get("completed_laps"),
        "fastest_lap": rd.get("fastest_lap"),
    }
    # incidents from events where type incident
    incidents = [
        e
        for e in (rd.get("events") or [])
        if "incident" in str(e.get("type", "")).lower() or "Incident" in str(e.get("type", ""))
    ]

    # reproducibility info
    reproducibility = {
        "seed": seed,
        "race_id": race_id,
        "track_id": track.id,
        "total_laps": total_laps,
        "model_version": MODEL_VERSION,
        "race_engine_version": RACEENGINE_VERSION,
        "note": "Same seed+config+versions = bit-identical within engine tolerance",
    }

    api_result: dict[str, Any] = {
        "simulation_id": rd.get("simulation_id") or f"sim_{race_id}_{seed}",
        "race_id": race_id,
        "seed": seed,
        "track_id": track.id,
        "total_laps": total_laps,
        "results": rd.get("results"),
        "classification": classification,
        "lap_summary": lap_summary,
        "incidents": incidents,
        "strategy_summary": {
            "enabled": bool(enable_strategy),
            "note": "PRIOR_ONLY beyond pit_tyre; see /strategy/evaluate",
        },
        "provenance": _provenance(seed, race_id, config),
        "model_versions": {
            "model_version": MODEL_VERSION,
            "race_engine_version": RACEENGINE_VERSION,
            "simulation_version": SIMULATION_VERSION,
        },
        "evidence_tiers": _provenance(seed, race_id, config)["evidence_tiers"],
        "warnings": [],
        "reproducibility": reproducibility,
        "events": rd.get("events", [])[:200],  # cap for payload size
        "telemetry": rd.get("telemetry", [])[:200],
        "runtime": {"elapsed_seconds": elapsed, "engine": "RaceEngine"},
        "raw": rd,
    }
    # warnings for PRIOR_ONLY
    if enable_strategy:
        api_result["warnings"].append(
            "strategy is PRIOR_ONLY: not calibrated, prior assumptions only"
        )
    if enable_setup:
        api_result["warnings"].append("setup is PRIOR_ONLY: model dials, not historical data")
    if enable_weather and race_id:
        api_result["warnings"].append(
            "historical weather is PRIOR_ONLY: no per-race observed weather injected"
        )
    if enable_race_control:
        api_result["warnings"].append("historical race control is PRIOR_ONLY: prior policy only")

    return api_result
