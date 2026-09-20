"""Isolated RNG stream for Race Control — deterministic, reproducible."""
from __future__ import annotations

import hashlib

import numpy as np


RACE_CONTROL_RNG_OFFSET = 600  # isolated from weather(500), tyre, driver streams


def race_control_seed(base_seed: int, sim_idx: int, lap: int | None = None) -> int:
    """Derive deterministic seed for race-control stream."""
    # base + offset + sim_idx*1000 preserves per-sim contract
    s = base_seed + RACE_CONTROL_RNG_OFFSET + sim_idx * 1000
    if lap is not None:
        s += lap * 7919  # prime to separate laps
    return s & 0xFFFFFFFF


def race_control_rng(base_seed: int, sim_idx: int, lap: int | None = None) -> np.random.Generator:
    return np.random.default_rng(race_control_seed(base_seed, sim_idx, lap))


def deterministic_event_id(race_id: str, lap: int, counter: int) -> str:
    """Deterministic unique event id: race_id:lap:counter hex."""
    raw = f"{race_id}:{lap}:{counter}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"RC:{race_id}:{lap:04d}:{counter:03d}:{h}"
