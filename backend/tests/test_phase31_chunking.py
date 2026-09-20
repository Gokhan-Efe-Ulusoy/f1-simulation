"""Phase 31 — Deterministic chunking matrix (order/worker/retry independent)."""
from __future__ import annotations

import pytest

from app.services.montecarlo_service import _build_scenario_for_montecarlo, _get_calibration_state
from app.simulation.performance.chunked_montecarlo import chunk_ranges, run_chunked
from app.simulation.performance.vectorized_montecarlo import VectorizedMonteCarlo


def _setup():
    scen = _build_scenario_for_montecarlo("2024-bahrain")
    calib = _get_calibration_state()
    return calib, scen


def _win_dict(drivers):
    return {k: round(v["win_probability"], 9) for k, v in drivers.items()}


@pytest.mark.parametrize("seed", [42, 43])
@pytest.mark.parametrize("N", [10, 20])
@pytest.mark.parametrize("cs", [1, 10, 20])
def test_chunk_equivalence(seed, N, cs):
    calib, scen = _setup()
    if cs > N:
        pytest.skip("chunk larger than N")
    e = VectorizedMonteCarlo(calib, scen, seed=seed)
    raw = e.run(simulations=N)
    c = run_chunked(calib, scen, seed=seed, total=N, chunk_size=cs)
    assert _win_dict(raw["drivers"]) == _win_dict(c["drivers"])
    # podium too
    for k in raw["drivers"]:
        assert abs(raw["drivers"][k]["podium_probability"] - c["drivers"][k]["podium_probability"]) < 1e-9


def test_order_independence():
    calib, scen = _setup()
    c_seq = run_chunked(calib, scen, seed=42, total=20, chunk_size=5, execution_order=[0, 1, 2, 3])
    c_shuf = run_chunked(calib, scen, seed=42, total=20, chunk_size=5, execution_order=[3, 0, 2, 1])
    assert _win_dict(c_seq["drivers"]) == _win_dict(c_shuf["drivers"])
    assert c_seq["aggregate_hash"] == c_shuf["aggregate_hash"]


def test_worker_independence_simulated():
    # Simulate 1 vs 2 vs 4 workers by different chunk sizes covering same N
    calib, scen = _setup()
    c1 = run_chunked(calib, scen, seed=42, total=20, chunk_size=20)
    c2 = run_chunked(calib, scen, seed=42, total=20, chunk_size=10)
    c4 = run_chunked(calib, scen, seed=42, total=20, chunk_size=5)
    assert _win_dict(c1["drivers"]) == _win_dict(c2["drivers"]) == _win_dict(c4["drivers"])


def test_retry_determinism_chunk():
    calib, scen = _setup()
    c1 = run_chunked(calib, scen, seed=42, total=20, chunk_size=10)
    # retry chunk 1: re-run that chunk range alone and compare hash
    from app.simulation.performance.vectorized_montecarlo import VectorizedMonteCarlo as VMC

    e = VMC(calib, scen, seed=42)
    r1 = e.run(simulations=10, start_index=10, return_arrays=True)
    e2 = VMC(calib, scen, seed=42)
    r2 = e2.run(simulations=10, start_index=10, return_arrays=True)
    import numpy as np

    assert np.array_equal(r1["_arrays"]["positions"], r2["_arrays"]["positions"])
    assert _win_dict(c1["drivers"]) is not None


def test_manifest():
    calib, scen = _setup()
    c = run_chunked(calib, scen, seed=42, total=20, chunk_size=5)
    m = c["manifest"]
    assert m["base_seed"] == 42
    assert m["total_samples"] == 20
    assert m["chunk_size"] == 5
    assert len(m["chunks"]) == 4
    assert m["deterministic"] is True
    assert "aggregate_hash" in m
    # no timestamps in hash
    assert all("result_hash" in ch for ch in m["chunks"])


def test_different_seed_different():
    calib, scen = _setup()
    c1 = run_chunked(calib, scen, seed=42, total=20, chunk_size=10)
    c2 = run_chunked(calib, scen, seed=43, total=20, chunk_size=10)
    assert _win_dict(c1["drivers"]) != _win_dict(c2["drivers"])


def test_chunk_ranges_validation():
    with pytest.raises(ValueError):
        chunk_ranges(10, 0)
    with pytest.raises(ValueError):
        chunk_ranges(10, 6000)
    assert chunk_ranges(10, 3) == [(0, 3), (3, 3), (6, 3), (9, 1)]
