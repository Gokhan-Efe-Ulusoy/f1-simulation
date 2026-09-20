"""Sprint-weekend / session abstractions (Phase 8).

Minimal session orchestration sharing team/driver/car/track/weekend
objects. Qualifying is a pace-model stub (Q1/Q2/Q3-ready structure);
sprint and main race delegate to RaceEngine. All draws use dedicated
streams derived from the weekend seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from app.simulation.core.random import RandomProvider
from app.simulation.core.state import SessionType


class WeekendFormat(str, Enum):
    """Supported weekend formats."""

    STANDARD = "standard"
    SPRINT = "sprint"


@dataclass
class SessionResult:
    """Classification of a single session."""

    session_type: SessionType
    seed: int | None
    order: list[str] = field(default_factory=list)  # driver ids, best first
    best_times: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RaceWeekend:
    """A race weekend sharing context across sessions."""

    weekend_id: str
    track_id: str
    format: WeekendFormat = WeekendFormat.STANDARD
    sessions: dict[str, SessionResult] = field(default_factory=dict)

    def record(self, result: SessionResult) -> None:
        """Store a completed session result."""
        key = result.session_type.value if hasattr(
            result.session_type, "value") else str(result.session_type)
        self.sessions[key] = result

    def get(self, session_type: SessionType) -> SessionResult | None:
        """Fetch a session result if present."""
        key = session_type.value if hasattr(session_type, "value") else str(session_type)
        return self.sessions.get(key)


def _stream_for(seed: int | None, name: str) -> np.random.Generator:
    stream_seed = None
    if seed is not None:
        stream_seed = hash((seed, name)) & 0xFFFFFFFF
    return np.random.default_rng(stream_seed)


def run_qualifying_stub(
    drivers,
    cars,
    track,
    seed: int | None = None,
    session_type: SessionType = SessionType.QUALIFYING,
) -> SessionResult:
    """Pace-model qualifying stub with Q1/Q2/Q3-ready output shape.

    Orders drivers by car+driver pace plus small deterministic noise.
    Returns per-segment cuts (top15/top10) for future extension.
    """
    rng = _stream_for(seed, "qualifying")
    pace: dict[str, float] = {}
    for driver in drivers:
        car = cars.get(driver.id)
        car_perf = car.calculate_performance_index("balanced") if car else 75.0
        skill = driver.get_effective_skill(
            track_id=getattr(track, "id", "track"), weather="dry",
            session_type="qualifying",
        )
        noise = float(rng.normal(0.0, 1.5))
        pace[driver.id] = (skill + car_perf) / 2.0 + noise
    order = sorted(pace, key=lambda d: pace[d], reverse=True)
    base = float(getattr(track, "reference_lap_time", 90.0))
    best_times = {d: base - (pace[d] - 75.0) * 0.12 for d in order}
    return SessionResult(
        session_type=session_type,
        seed=seed,
        order=order,
        best_times=best_times,
        metadata={
            "q1_cut": order[:15],
            "q2_cut": order[:10],
            "pole": order[0] if order else None,
        },
    )


def run_sprint(
    config,
    drivers,
    cars,
    track,
    rng: RandomProvider,
    sprint_laps: int | None = None,
):
    """Run a sprint (shortened race) sharing the weekend context."""
    from app.simulation.core.race_engine import RaceEngine

    laps = sprint_laps or max(5, int(config.total_laps / 3))
    sprint_cfg = config.model_copy(update={
        "simulation_id": f"{config.simulation_id}_sprint",
        "session_type": SessionType.SPRINT,
        "total_laps": laps,
    })
    engine = RaceEngine()
    return engine.simulate_race(sprint_cfg, drivers, cars, track, rng)


def run_weekend(
    weekend_id: str,
    format: WeekendFormat,
    config,
    drivers,
    cars,
    track,
    seed: int | None = None,
):
    """Run a full weekend: practice(skip) -> qualifying -> [sprint] -> race."""
    from app.simulation.core.race_engine import RaceEngine

    weekend = RaceWeekend(weekend_id=weekend_id, track_id=track.id, format=format)
    quali = run_qualifying_stub(drivers, cars, track, seed=seed)
    weekend.record(quali)

    base_seed = seed if seed is not None else 0
    if format == WeekendFormat.SPRINT:
        sprint_cfg = config.model_copy(update={
            "simulation_id": f"{weekend_id}_sprint",
            "session_type": SessionType.SPRINT,
            "total_laps": max(5, int(config.total_laps / 3)),
        })
        sprint_res = RaceEngine().simulate_race(
            sprint_cfg, drivers, cars, track, RandomProvider(seed=base_seed + 1))
        weekend.record(SessionResult(
            session_type=SessionType.SPRINT, seed=base_seed + 1,
            order=[r.driver_id for r in sorted(sprint_res.results, key=lambda r: r.position)],
            metadata={"race_result": sprint_res.model_dump()},
        ))

    race_res = RaceEngine().simulate_race(
        config, drivers, cars, track, RandomProvider(seed=base_seed + 2))
    weekend.record(SessionResult(
        session_type=SessionType.RACE, seed=base_seed + 2,
        order=[r.driver_id for r in sorted(race_res.results, key=lambda r: r.position)],
        metadata={"race_result": race_res.model_dump()},
    ))
    return weekend
