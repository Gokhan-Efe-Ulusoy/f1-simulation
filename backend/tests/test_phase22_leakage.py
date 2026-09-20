"""Phase 22 — Leakage tests (no future information in the decision layer)."""
import pytest

from app.simulation.replay.historical_observer import assert_no_future_fields, build_observation
from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.state_builder import load_historical_race
from app.simulation.replay.validation import leakage_probe, walk_forward
from app.simulation.scenario.models import Intervention, ScenarioSpec
from app.simulation.scenario.validation import ScenarioValidationError


@pytest.fixture(scope="module")
def engine():
    return ReplayEngine(seed=42, simulations=60)


def test_as_of_strict_before_race_date():
    for race_id in ("2024-bahrain", "2023-monaco", "2024-monza"):
        try:
            hrace = load_historical_race(race_id)
        except ValueError:
            continue
        assert hrace.as_of < hrace.race_date, race_id


def test_observation_carries_no_future():
    hrace = load_historical_race("2024-bahrain")
    for lap in (0, 5):
        assert assert_no_future_fields(build_observation(hrace, lap)) == []


def test_future_params_rejected_at_validation(engine):
    base = engine.scenario_for_race(engine.load_race("2024-bahrain"), laps=6)
    spec = ScenarioSpec(
        spec_id="p22-leak", baseline_scenario_id=base.scenario_id,
        interventions=[Intervention(family="weather", op="SET_VALUE",
                                    target="race", parameter="future_result",
                                    value=1.0)],
        seed=42, simulations=60,
    )
    with pytest.raises(ScenarioValidationError):
        from app.simulation.scenario.compiler import compile_spec
        compile_spec(base, spec)


def test_injected_future_blocks_are_inert(engine):
    base = engine.scenario_for_race(engine.load_race("2024-bahrain"), laps=6)
    probe = leakage_probe(base, seed=42, simulations=60)
    assert probe["violations"] == []
    assert probe["max_abs_win_delta"] == 0.0


def test_walk_forward_windows_leakage_safe():
    rows = walk_forward(["2024-bahrain", "2024-jeddah"], seed=42, simulations=60, laps=6)
    assert len(rows) == 2
    for row in rows:
        assert row["training_end"] < row["target_date"]
        assert row["baseline_fingerprint"]
        assert "future" in row["observations_excluded"]
