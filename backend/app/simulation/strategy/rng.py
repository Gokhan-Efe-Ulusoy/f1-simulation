"""Isolated RNG for Strategy — deterministic, leakage-safe."""
from __future__ import annotations

import numpy as np

STRATEGY_RNG_OFFSET = 700  # isolated from weather 500, race_control 600, AR1 100


def strategy_seed(base_seed: int, sim_idx: int, lap: int | None = None) -> int:
    s = base_seed + STRATEGY_RNG_OFFSET + sim_idx * 1000
    if lap is not None:
        s += lap * 7919
    return s & 0xFFFFFFFF


def strategy_rng(base_seed: int, sim_idx: int, lap: int | None = None) -> np.random.Generator:
    return np.random.default_rng(strategy_seed(base_seed, sim_idx, lap))
