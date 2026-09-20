"""Batch state for vectorized Monte Carlo — shape (N, drivers)."""
from __future__ import annotations

import numpy as np
from typing import Dict, List

class BatchState:
    """Holds batched race state for N simulations.

    Attributes:
        N: number of simulations
        D: number of drivers
        driver_ids: list of driver ids (length D)
        constructor_ids: list per driver
        driver_idx: driver_id -> idx
        positions: (N, D) int — current positions (1..D, DNF = D+1)
        times: (N, D) float — total time per driver
        gaps: (N, D) float — gap ahead (not used in vectorized, but for completeness)
        dnf: (N, D) bool — DNF state
        tyre_age: (N, D) int
        noise: (N, D) float — AR(1) state
        laps: (N,) int — current lap
    """

    def __init__(self, driver_ids: List[str], constructor_ids: List[str], N: int):
        self.N = N
        self.D = len(driver_ids)
        self.driver_ids = driver_ids
        self.constructor_ids = constructor_ids
        self.driver_idx = {did: i for i, did in enumerate(driver_ids)}
        # Precompute constructor groups for correlated sampling
        self.constructor_to_indices: Dict[str, List[int]] = {}
        for idx, cid in enumerate(constructor_ids):
            self.constructor_to_indices.setdefault(cid, []).append(idx)

        # State arrays
        self.positions = np.zeros((N, self.D), dtype=np.int16)
        self.times = np.zeros((N, self.D), dtype=np.float32)
        self.dnf = np.zeros((N, self.D), dtype=bool)
        self.noise = np.zeros((N, self.D), dtype=np.float32)
        self.tyre_age = np.zeros((N, self.D), dtype=np.int16)
        # Tyre state for Phase 16
        self.tyre_compound = np.zeros((N, self.D), dtype=np.int8)  # 0=UNKNOWN,1=SOFT etc.
        self.tyre_stint = np.zeros((N, self.D), dtype=np.int16)
        self.tyre_available = np.zeros((N, self.D), dtype=bool)
        self.tyre_grip = np.ones((N, self.D), dtype=np.float32)
        self.tyre_degradation = np.zeros((N, self.D), dtype=np.float32)
        # Weather state for Phase 17 — race-level shared across drivers (N, L) or (N,) per lap
        self.weather_wetness = np.zeros((N,), dtype=np.float32)  # per-sim current wetness (race-level)  # noqa: E501
        self.weather_grip = np.ones((N,), dtype=np.float32)
        self.weather_track_temp = np.full((N,), 35.0, dtype=np.float32)
        self.weather_rainfall = np.zeros((N,), dtype=np.float32)
        # Race Control state for Phase 18 — race-level shared across drivers (N,) per lap + (N,L,S) trajectories
        self.race_control_phase = np.zeros((N,), dtype=np.int8)  # current lap phase (int encoded)
        self.race_control_phase_traj = None  # (N,L) allocated when L known
        self.race_control_sector = None  # (N,L,S) when needed
        self.race_control_drs_mask = None  # (N,L) bool
        # Strategy state for Phase 19 — per-driver per-lap decision (N,D) or per-driver schedule
        self.strategy_enabled = False
        self.strategy_pit_laps = None  # (N,D) or dict per driver
        self.strategy_chosen_compound = None

    def initialize_grid(self, grid_order: List[str]):
        """Set initial positions from grid order (same for all N)."""
        # grid_order is list of driver_ids, pole first
        for pos, did in enumerate(grid_order, start=1):
            idx = self.driver_idx[did]
            self.positions[:, idx] = pos
        # Gaps: not needed for vectorized, but initialize
        self.times[:, :] = 0.0

    def get_constructor_indices(self, cid: str) -> List[int]:
        return self.constructor_to_indices.get(cid, [])
