"""Phase 22 — Sensitivity engine tests (deterministic grids, no explosion)."""
import pytest

from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.sensitivity import MAX_GRID_POINTS, SensitivityEngine


@pytest.fixture(scope="module")
def baseline():
    eng = ReplayEngine(seed=42, simulations=60)
    hrace = eng.load_race("2024-bahrain")
    return eng.scenario_for_race(hrace, laps=6)


@pytest.fixture(scope="module")
def did(baseline):
    return baseline.drivers[0]["driver_id"]


def test_ofat_deterministic_grid(baseline, did):
    eng = SensitivityEngine(seed=42, simulations=60)
    r1 = eng.run_ofat(baseline, "p22-ofat", family="setup", target=did,
                      parameter="front_wing", values=[3.0, 4.0, 5.0, 6.0, 7.0])
    r2 = eng.run_ofat(baseline, "p22-ofat", family="setup", target=did,
                      parameter="front_wing", values=[3.0, 4.0, 5.0, 6.0, 7.0])
    assert len(r1.points) == 5
    assert [p.value for p in r1.points] == [3.0, 4.0, 5.0, 6.0, 7.0]
    assert r1.baseline_fingerprint == r2.baseline_fingerprint
    assert [p.l1_finish_distribution for p in r1.points] == [
        p.l1_finish_distribution for p in r2.points]
    assert r1.method == "one_factor_at_a_time"
    assert all(p.evidence_tier == "PRIOR_ONLY" for p in r1.points)


def test_ofat_cap_enforced(baseline, did):
    eng = SensitivityEngine(seed=42, simulations=60)
    with pytest.raises(ValueError):
        eng.run_ofat(baseline, "p22-big", family="setup", target=did,
                     parameter="front_wing",
                     values=[float(v) for v in range(MAX_GRID_POINTS + 1)])


def test_bounded_grid_2d(baseline, did):
    eng = SensitivityEngine(seed=42, simulations=60)
    res = eng.run_grid(baseline, "p22-grid",
                       axes={"front_wing": [4.0, 6.0], "rear_wing": [4.0, 6.0]},
                       family="setup", target=did)
    assert len(res.points) == 4
    assert res.method == "bounded_grid_2d"
    with pytest.raises(ValueError):
        eng.run_grid(baseline, "p22-gridbig",
                     axes={"front_wing": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                           "rear_wing": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]},
                     family="setup", target=did)
    with pytest.raises(ValueError):
        eng.run_grid(baseline, "p22-grid3",
                     axes={"a": [1.0], "b": [1.0], "c": [1.0]},
                     family="setup", target=did)


def test_ofat_pit_lap_sweep_moves(baseline, did):
    eng = SensitivityEngine(seed=42, simulations=60)
    res = eng.run_ofat(baseline, "p22-pitlap", family="strategy", target=did,
                       parameter="pit_laps", values=[[2], [3], [4], [5]])
    assert len(res.points) == 4
    assert any(p.l1_finish_distribution > 0 for p in res.points)
    assert res.limitations  # honest bounds documented
