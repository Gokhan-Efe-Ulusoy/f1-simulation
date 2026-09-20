"""Phase 22 — Historical replay tests (state, checkpoints, cutoff, missingness).

Convention: 2024-bahrain, shortened horizons, vectorized path (N=60).
"""
import pytest

from app.simulation.replay.checkpoints import checkpoint_lap, valid_checkpoints
from app.simulation.replay.historical_observer import (
    assert_no_future_fields,
    build_observation,
)
from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.state_builder import (
    as_of_for_race_date,
    build_scenario_for_race,
    load_historical_race,
)


@pytest.fixture(scope="module")
def hrace():
    return load_historical_race("2024-bahrain")


@pytest.fixture(scope="module")
def engine():
    return ReplayEngine(seed=42, simulations=60)


def test_historical_race_loads_with_cutoff(hrace):
    assert hrace.race_id == "2024-bahrain"
    assert hrace.race_date == "2024-03-02"
    assert hrace.as_of == as_of_for_race_date("2024-03-02")
    assert hrace.as_of < hrace.race_date
    assert hrace.observed_result_validation_only is True
    assert len(hrace.grid_order) == 20
    assert len(hrace.drivers) == 20


def test_total_laps_non_identifiable_for_bahrain(hrace):
    # Canonical scheduled_laps is null for 2024-bahrain: must not be invented.
    assert hrace.total_laps is None
    assert hrace.total_laps_tier == "NON_IDENTIFIABLE"
    assert "total_laps" in hrace.unavailable


def test_observation_excludes_future_pre_race(hrace):
    obs = build_observation(hrace, lap=0)
    assert obs.realized_result_excluded is True
    assert assert_no_future_fields(obs) == []
    # Pre-race model priors are explicit, not observations.
    assert obs.race_control_phase.evidence_tier == "PRIOR_ONLY"
    assert obs.tyre_age.value == 0
    # Never-available history is explicit.
    assert obs.setup_state.value is None
    assert obs.setup_state.evidence_tier == "NON_IDENTIFIABLE"
    assert obs.weather_current.evidence_tier == "NON_IDENTIFIABLE"
    assert obs.fuel_state.evidence_tier == "NON_IDENTIFIABLE"


def test_observation_in_race_histories_not_identifiable(hrace):
    obs = build_observation(hrace, lap=10)
    assert obs.lap == 10
    assert obs.pit_history_observed_until_t.value is None
    assert obs.pit_history_observed_until_t.evidence_tier == "NON_IDENTIFIABLE"
    assert obs.incident_history_observed_until_t.evidence_tier == "NON_IDENTIFIABLE"
    assert obs.race_control_phase.evidence_tier == "NON_IDENTIFIABLE"
    assert assert_no_future_fields(obs) == []


def test_scenario_excludes_observed_result(hrace):
    sc = build_scenario_for_race(hrace, laps=6)
    blob = sc.model_dump_json()
    assert "final_position" not in blob
    assert hrace.as_of == sc.as_of
    assert sc.race_distance["laps"] == 6


def test_checkpoints_valid_for_race_length():
    cps = valid_checkpoints(6)
    assert "pre_race" in cps and "finish" in cps
    assert "lap_10" not in cps and "lap_5" in cps
    assert checkpoint_lap("finish", 6) == 6
    assert checkpoint_lap("lap_5", 6) == 5
    cps58 = valid_checkpoints(58)
    assert "lap_50" in cps58 and "finish" in cps58
    with pytest.raises(ValueError):
        checkpoint_lap("lap_xyz", 58)


def test_replay_baseline_runs(engine):
    rep = engine.replay("2024-bahrain", laps=6, with_checkpoints=False)
    assert rep.race_id == "2024-bahrain"
    assert rep.seed == 42 and rep.simulations == 60
    assert len(rep.baseline_fingerprint) == 16
    prov = rep.provenance
    assert prov["versions"]["REPLAY_MODEL_VERSION"] == "replay-v1.0.0"
    assert prov["versions"]["RACEENGINE_VERSION"] == "raceengine-v2.2.0"
    assert prov["versions"]["STRATEGY_MODEL_VERSION"] == "strategy-v1.1.0"
    assert rep.evidence_summary["weather"] == "NON_IDENTIFIABLE"
    assert rep.evidence_summary["setup"] == "NON_IDENTIFIABLE"


def test_replay_checkpoints_run(engine):
    rep = engine.replay("2024-bahrain", laps=6, with_checkpoints=True)
    names = [c.name for c in rep.checkpoint_results]
    assert names == valid_checkpoints(6)[1:]  # pre_race (lap 0) has no leg
    assert all(len(c.fingerprint) == 16 for c in rep.checkpoint_results)
    assert all(c.simulations == 60 and c.seed == 42 for c in rep.checkpoint_results)


def test_arbitrary_checkpoint(engine):
    ck = engine.checkpoint("2024-bahrain", lap=3)
    assert ck.lap == 3 and ck.name == "lap_3"
    assert len(ck.fingerprint) == 16


def test_deviation_metrics_honest(engine):
    rep = engine.replay("2024-bahrain", laps=6, with_checkpoints=False)
    dev = rep.deviation_metrics
    assert dev.observed_winner  # canonical result exists
    assert dev.finish_mae is not None and dev.finish_mae_drivers == 20
    assert dev.pit_count_mismatch == "NON_IDENTIFIABLE"
    assert dev.lap_time_mae == "NON_IDENTIFIABLE"
    assert dev.coverage["non_identifiable"]
    assert len(rep.observed_result) == 20


def test_unknown_race_raises(engine):
    with pytest.raises(ValueError):
        engine.replay("9999-nowhere")
