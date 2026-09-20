"""Phase 22 — Physical sanity tests (monotonicity with real propagation)."""
import pytest

from app.simulation.replay import sanity
from app.simulation.replay.replay_engine import ReplayEngine


@pytest.fixture(scope="module")
def factory_and_driver():
    eng = ReplayEngine(seed=42, simulations=60)
    hrace = eng.load_race("2024-bahrain")

    def factory():
        return eng.scenario_for_race(hrace, laps=6)

    return factory, hrace.grid_order[0]


@pytest.fixture(scope="module")
def all_checks(factory_and_driver):
    factory, did = factory_and_driver
    return sanity.run_all_sanity(factory, did)


def test_all_sanity_checks_run(all_checks):
    assert len(all_checks) == 6
    assert {c.name for c in all_checks} == {
        "pit_loss_monotonic", "extra_stop_cost", "pace_monotonic",
        "aero_grip_monotonic", "wet_weather_effect", "tyre_compound_effect",
    }


def test_pit_loss_monotonic(all_checks):
    c = {x.name: x for x in all_checks}["pit_loss_monotonic"]
    assert c.status == "PASS", c.detail
    assert c.measured["delta"] >= -0.75


def test_extra_stop_cost(all_checks):
    c = {x.name: x for x in all_checks}["extra_stop_cost"]
    assert c.status == "PASS", c.detail
    assert c.measured["delta"] >= -0.75


def test_pace_monotonic(all_checks):
    c = {x.name: x for x in all_checks}["pace_monotonic"]
    assert c.status == "PASS", c.detail


def test_aero_grip_monotonic(all_checks):
    c = {x.name: x for x in all_checks}["aero_grip_monotonic"]
    assert c.status == "PASS", c.detail


def test_wet_weather_effect(all_checks):
    c = {x.name: x for x in all_checks}["wet_weather_effect"]
    assert c.status == "PASS", c.detail
    assert c.measured["d_mean_wetness"] > 0


def test_tyre_compound_effect(all_checks):
    c = {x.name: x for x in all_checks}["tyre_compound_effect"]
    assert c.status == "PASS", c.detail
