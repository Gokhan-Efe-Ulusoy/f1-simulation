"""RaceEngine v1.1.0 — performance-optimized, scientific equivalence preserved.

Wraps v14 reference with vectorized Monte Carlo, cached calibration, batch RNG, Numba kernels.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.simulation.race_engine_v14 import RaceEngine as ReferenceEngine
from app.simulation.scenario_v14 import Scenario
from app.simulation.performance.vectorized_montecarlo import VectorizedMonteCarlo
from app.simulation.calibration_state import build_calibration_state

RACEENGINE_VERSION = "raceengine-v1.1.0"

class RaceEngineV15(ReferenceEngine):
    """Optimized engine: same API, faster via vectorized path."""

    def __init__(self, calibration: str = "calibration-v1.0.0", dataset: str = "f1-dataset-v1.1", seed: int = 42, use_vectorized: bool = True):  # noqa: E501
        super().__init__(calibration=calibration, dataset=dataset, seed=seed)
        self.version = RACEENGINE_VERSION
        self.use_vectorized = use_vectorized

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed
        # Build calibration state once (cached via calibration_api)
        calib_state = self._build_calibration_state(scenario)
        # Choose path
        if self.use_vectorized and simulations >= 50:
            # Vectorized path for large N
            runner = VectorizedMonteCarlo(calibration_state=calib_state, scenario=scenario, seed=seed)  # noqa: E501
            # Need to time
            start = time.perf_counter()
            result = runner.run(simulations=simulations)
            elapsed = time.perf_counter() - start
            result["provenance"]["engine_version"] = self.version
            result["provenance"]["seed"] = seed
            result["scenario"] = scenario.model_dump()
            result["calibration_state"] = calib_state
            result["performance"] = {"elapsed": elapsed, "simulations": simulations, "sim_per_sec": simulations/elapsed if elapsed>0 else 0}  # noqa: E501
            return result
        else:
            # Fallback to reference for small N or exact equivalence testing
            return super().simulate(scenario, simulations=simulations, seed=seed)

    # Keep other methods from reference
