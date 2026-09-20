"""Phase 22 — Counterfactual replay tests (isolation, pit-loss, CRN)."""
import pytest

from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.scenario.compiler import compile_spec
from app.simulation.scenario.engine import ScenarioEngine
from app.simulation.scenario.models import Intervention, ScenarioSpec
from app.simulation.scenario.validation import ScenarioValidationError


@pytest.fixture(scope="module")
def engine():
    return ReplayEngine(seed=42, simulations=60)


@pytest.fixture(scope="module")
def hrace(engine):
    return engine.load_race("2024-bahrain")


@pytest.fixture(scope="module")
def did(hrace):
    return hrace.grid_order[0]


def _cf(engine, did, ivs, tag):
    return engine.counterfactual(
        "2024-bahrain", ivs, experiment_id=f"p22-{tag}", laps=6,
    )


def test_counterfactual_isolation_single_driver_pit(engine, did):
    exp = _cf(engine, did, [Intervention(
        family="strategy", op="SET_VALUE", target=did,
        parameter="pit_laps", value=[3])], "isol")
    assert exp.baseline_fingerprint != exp.counterfactual_fingerprint
    eff = {e.driver_id: e for e in exp.comparison.driver_deltas}[did]
    assert eff.l1_finish_distribution > 0
    assert exp.crn_manifest.same_seed is True
    assert exp.crn_manifest.baseline_seed == exp.crn_manifest.counterfactual_seed == 42
    assert exp.crn_manifest.stream_manifest  # documents actual streams
    assert exp.comparison.common_random_numbers is True


def test_pit_loss_disabled_baseline_equivalence():
    # v21 engine vs v22 engine on a pit-loss-free scenario: dynamics identical.
    from app.simulation.race_engine_v21 import ScenarioAwareRaceEngine as V21
    from app.simulation.race_engine_v22 import ReplayAwareRaceEngine as V22
    from app.simulation.replay.state_builder import build_scenario_for_race, load_historical_race

    hrace = load_historical_race("2024-bahrain")
    r21 = V21(seed=42).simulate(build_scenario_for_race(hrace, laps=6), simulations=60, seed=42)
    r22 = V22(seed=42).simulate(build_scenario_for_race(hrace, laps=6), simulations=60, seed=42)
    for did, d in r21["drivers"].items():
        assert abs(d["win_probability"] - r22["drivers"][did]["win_probability"]) < 1e-12
        assert abs(d["expected_finish"] - r22["drivers"][did]["expected_finish"]) < 1e-12
    assert r22["pit_loss"]["enabled"] is False
    assert r22["provenance"]["pit_loss_enabled"] is False


def test_pit_loss_enabled_propagates(engine, hrace, did):
    base = engine.scenario_for_race(hrace, laps=6)
    eng = ScenarioEngine(seed=42, simulations=60)
    laps = 3

    def _spec(loss):
        return ScenarioSpec(
            spec_id=f"p22-loss{loss}", baseline_scenario_id=base.scenario_id,
            interventions=[
                Intervention(family="strategy", op="SET_VALUE", target=did,
                             parameter="pit_laps", value=[laps]),
                Intervention(family="strategy", op="SET_VALUE", target=did,
                             parameter="pit_loss_seconds", value=loss),
            ],
            seed=42, simulations=60,
        )

    r_free = eng.run_spec(engine.scenario_for_race(hrace, laps=6), _spec(0.0))
    r_cost = eng.run_spec(engine.scenario_for_race(hrace, laps=6), _spec(24.4))
    assert r_free.counterfactual_fingerprint != r_cost.counterfactual_fingerprint
    f_free = {e.driver_id: e for e in r_free.comparison.driver_effects}[did]
    f_cost = {e.driver_id: e for e in r_cost.comparison.driver_effects}[did]
    assert f_free.l1_finish_distribution > 0 or f_cost.l1_finish_distribution > 0
    # Same schedule, only loss differs: costly leg must not be systematically better.
    assert (f_cost.d_expected_finish - f_free.d_expected_finish) >= -0.75
    # Provenance records the channel.
    _, trace, _ = compile_spec(base, _spec(24.4))
    assert any(t.parameter == "pit_loss_seconds" for t in trace)
    assert "hypothetical_modifiers.strategy.pit_loss_seconds" in trace[1].modifier_path


def test_pit_loss_validation_bounds(hrace, engine):
    base = engine.scenario_for_race(hrace, laps=6)
    for bad in (99.0, -1.0, "lots"):
        spec = ScenarioSpec(
            spec_id="p22-badloss", baseline_scenario_id=base.scenario_id,
            interventions=[Intervention(family="strategy", op="SET_VALUE",
                                        target="all", parameter="pit_loss_seconds",
                                        value=bad)],
            seed=42, simulations=60,
        )
        with pytest.raises(ScenarioValidationError):
            compile_spec(base, spec)


def test_pit_loss_composes_with_schedule_no_conflict(engine, hrace, did):
    base = engine.scenario_for_race(hrace, laps=6)
    spec = ScenarioSpec(
        spec_id="p22-compose", baseline_scenario_id=base.scenario_id,
        interventions=[
            Intervention(family="strategy", op="SET_VALUE", target=did,
                         parameter="pit_laps", value=[3]),
            Intervention(family="strategy", op="SET_VALUE", target=did,
                         parameter="pit_loss_seconds", value=10.0),
        ],
        seed=42, simulations=60,
    )
    compiled, trace, _ = compile_spec(base, spec)
    assert len(trace) == 2
    assert compiled.hypothetical_modifiers["strategy"]["pit_loss_seconds"][did] == 10.0


def test_experiment_attribution_grounded(engine, did):
    exp = _cf(engine, did, [Intervention(
        family="driver", op="ADD_DELTA", target=did,
        parameter="pace_delta", value=0.5)], "attr")
    assert len(exp.attribution.what_changed) == 1
    assert exp.attribution.where_changed
    assert exp.attribution.downstream.direct
    assert exp.attribution.downstream.final
    assert "causal" in exp.attribution.disclaimer
    assert exp.attribution.evidence_tier == "PRIOR_ONLY"


def test_extended_comparison_quantiles_and_relative(engine, did):
    exp = _cf(engine, did, [Intervention(
        family="driver", op="ADD_DELTA", target=did,
        parameter="pace_delta", value=1.0)], "ext")
    comp = exp.comparison
    assert len(comp.driver_deltas) == 20
    eff = {e.driver_id: e for e in comp.driver_deltas}[did]
    assert eff.l1_finish_distribution > 0
    assert comp.unmeasurable["mean_lap_time"] == "NOT_TESTABLE"
    assert comp.unmeasurable["total_race_time"] == "NOT_TESTABLE"
    assert comp.pit_counts["evidence_tier"] == "PRIOR_ONLY"
