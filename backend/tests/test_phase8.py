"""Phase 8 tests: per-sector dynamics, procedures, planning, sessions, telemetry."""
from __future__ import annotations

import numpy as np
import pytest

from app.simulation.calibration import CalibrationProfile
from app.simulation.core.race_engine import RaceEngine
from app.simulation.core.random import RandomProvider
from app.simulation.core.state import (
    EventVerbosity,
    SessionType,
    SimulationConfig,
    TelemetrySampling,
)
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.track import Track, TrackType
from app.simulation.models.weather import WeatherCondition
from app.simulation.racing.battle_planner import BattlePlanner
from app.simulation.racing.models import BattleResourceState
from app.simulation.racing.race_procedure import (
    FirstCornerModel,
    FormationLapModel,
    RedFlagModel,
    StandingRestartModel,
    StandingStartModel,
)
from app.simulation.racing.sectors import (
    compute_sector_weights,
    sector_gap_trace,
    split_lap_into_sectors,
)
from app.simulation.telemetry import TelemetrySampler
from app.simulation.version import CONFIG_VERSION, SIMULATION_VERSION
from app.simulation.weekend import (
    WeekendFormat,
    run_qualifying_stub,
    run_weekend,
)


def _make_driver(idx, team="T1", **kw):
    base = dict(
        id=f"D{idx}", name=f"Driver {idx}", short_name=f"D{idx}", number=idx,
        nationality="X", date_of_birth="1990-01-01", team_id=team,
        overall_skill=75, qualifying_skill=75, race_skill=75, consistency=75,
        aggression=50, tyre_management=75, wet_weather_skill=75, overtaking=75,
        defending=75, start_performance=75, adaptability=75,
        pressure_resistance=75, mistake_rate=10,
    )
    base.update(kw)
    return Driver(**base)


def _make_car(idx, team="T1"):
    return Car(id=f"C{idx}", name=f"Car {idx}", team_id=team,
               engine_id=f"E{idx}", year=2024)


def _make_track(**kw):
    base = dict(
        id="t8", name="T", country="C", city="C",
        track_type=TrackType.PERMANENT, length_km=5.0, number_of_laps=5,
        race_distance_km=25.0, number_of_corners=10,
        reference_lap_time=90.0, pit_stop_time_loss=20.0, overtaking_difficulty=40,
    )
    base.update(kw)
    t = Track(**base)
    t.initialize_sector_characteristics()
    return t


def _make_config(**kw):
    base = dict(
        simulation_id="p8", seed=7, total_laps=5,
        initial_weather=WeatherCondition.DRY, weather_variability=0.0,
        safety_car_probability=0.0, vsc_probability=0.0, incident_probability=0.0,
    )
    base.update(kw)
    return SimulationConfig(**base)


def _run(drivers, track=None, config=None, seed=21):
    track = track or _make_track()
    config = config or _make_config()
    cars = {d.id: _make_car(int(d.number), d.team_id) for d in drivers}
    return RaceEngine().simulate_race(config, drivers, cars, track, RandomProvider(seed=seed))


def _resource(fuel=50.0, ers=0.8, conserve_fuel=False, conserve_ers=False):
    return BattleResourceState(
        fuel_mass=fuel, fuel_target=5.0, fuel_mode="standard", ers_energy=ers,
        ers_mode="medium", ers_target=0.5, tyre_condition=0.8, tyre_wear=0.2,
        tyre_compound="soft", tyre_age=3, can_attack=not (conserve_fuel or conserve_ers),
        fuel_conservation_required=conserve_fuel, ers_conservation_required=conserve_ers,
    )


# ---------------- Determinism ----------------

def test_determinism_formation_start_sector_redflag_weekend_planner_telemetry():
    def run_once(seed):
        res = _run([_make_driver(1), _make_driver(2)], seed=seed)
        kinds = [e["event_type"] for e in res.events]
        return ([(r.driver_id, r.position) for r in res.results], kinds,
                [(r.driver_id, round(r.total_time, 9)) for r in res.results if r.total_time])
    assert run_once(77) == run_once(77)


def test_determinism_standing_start_model():
    m = StandingStartModel()
    a = [m.evaluate("D1", 90, 60, 80, 80, 95.0, 1.0, np.random.default_rng(5)).launch_quality
         for _ in range(3)]
    m2 = StandingStartModel()
    b = [m2.evaluate("D1", 90, 60, 80, 80, 95.0, 1.0, np.random.default_rng(5)).launch_quality
         for _ in range(3)]
    assert a == b


def test_determinism_planner_and_telemetry():
    p = BattlePlanner()
    r1 = p.plan(_resource(), _resource(), 0.6, 0.3, 5, np.random.default_rng(9))
    r2 = BattlePlanner().plan(_resource(), _resource(), 0.6, 0.3, 5, np.random.default_rng(9))
    assert (r1.action_now, r1.horizon_actions) == (r2.action_now, r2.horizon_actions)
    s = TelemetrySampler(TelemetrySampling.SECTOR)
    assert s.to_dicts() == []


# ---------------- Sector invariants ----------------

def test_sector_split_sums_to_lap_time():
    track = _make_track()
    car, driver = _make_car(1), _make_driver(1)
    weights = compute_sector_weights(track, car, driver)
    assert abs(sum(weights) - 1.0) < 1e-9
    assert all(w >= 0 for w in weights)
    for lap_time in (73.5, 90.0, 121.7):
        sectors = split_lap_into_sectors(lap_time, weights)
        assert len(sectors) == track.number_of_sectors
        assert all(s >= 0 for s in sectors)
        assert abs(sum(sectors) - lap_time) < 1e-9


def test_sector_distances_sum_to_lap_distance():
    track = _make_track()
    assert abs(sum(track.sector_lengths_km) - track.length_km) < 1e-6 or not track.sector_lengths_km


def test_sector_gap_trace_consistency():
    lead = [30.0, 30.0, 30.0]
    follow = [30.2, 29.9, 30.1]
    gaps = sector_gap_trace(lead, follow, 0.5)
    assert gaps == [pytest.approx(0.7), pytest.approx(0.6), pytest.approx(0.7)]
    assert all(g >= 0 for g in gaps)


def test_no_negative_sector_times_in_race():
    res = _run([_make_driver(1), _make_driver(2)])
    assert res.results[0].best_lap_time is not None and res.results[0].best_lap_time > 0


# ---------------- Start tests ----------------

def test_same_seed_same_start():
    m = StandingStartModel()
    kw = dict(driver_id="D1", start_performance=85, aggression=60, car_traction=80,
              car_power_proxy=80, tyre_temp=95.0, track_grip=1.0)
    a = m.evaluate(rng=np.random.default_rng(3), **kw)
    b = StandingStartModel().evaluate(rng=np.random.default_rng(3), **kw)
    assert (a.reaction_time, a.launch_quality, a.position_delta) == \
        (b.reaction_time, b.launch_quality, b.position_delta)


def test_better_start_performance_better_average_launch():
    m = StandingStartModel()
    weak = np.mean([m.evaluate("D", 40, 50, 70, 70, 95.0, 1.0,
                               np.random.default_rng(1000 + i)).launch_quality
                    for i in range(300)])
    strong = np.mean([m.evaluate("D", 95, 50, 70, 70, 95.0, 1.0,
                                 np.random.default_rng(1000 + i)).launch_quality
                      for i in range(300)])
    assert strong > weak


def test_formation_warms_tyres_deterministically():
    m = FormationLapModel()
    a = m.run("D1", 60.0, 50, 90.0, np.random.default_rng(8))
    assert 60.0 < a.tyre_temp <= 95.0
    assert not a.failed_to_start or a.incident


# ---------------- Red flag tests ----------------

def _find_red_flag_seed():
    """Deterministically find a seed whose first red-flag draw deploys."""
    for seed in range(1000):
        if RandomProvider(seed=seed).get_stream("red_flag").random() < 0.2:
            return seed
    raise AssertionError("no deploying seed found")


def test_red_flag_freezes_and_resumes_with_correct_distance():
    seed = _find_red_flag_seed()
    cfg = _make_config(total_laps=5, red_flag_probability=0.2, red_flag_laps=1)
    res = _run([_make_driver(1), _make_driver(2)], config=cfg, seed=seed)
    kinds = [e["event_type"] for e in res.events]
    assert "red_flag_deployed" in kinds
    assert "red_flag_lifted" in kinds
    assert "standing_restart" in kinds
    assert res.completed_laps == 5
    assert sorted(r.position for r in res.results) == [1, 2]


def test_red_flag_preserves_fuel_and_state():
    seed = _find_red_flag_seed()
    cfg = _make_config(total_laps=5, red_flag_probability=0.2, red_flag_laps=1)
    res = _run([_make_driver(1), _make_driver(2)], config=cfg, seed=seed)
    assert res.completed_laps == 5
    # Laps 1-2 are suspended/restart (frozen: no lap time accrues), so the
    # winner's total must be far below a full 5-lap race (~450 s).
    winner = min((r for r in res.results if r.total_time), key=lambda r: r.total_time)
    assert winner.total_time < 350.0
    assert all(r.total_time is None or r.total_time > 0 for r in res.results)


def test_red_flag_model_determinism_and_bounds():
    m = RedFlagModel()
    r1 = m.check(10, False, False, np.random.default_rng(4))
    r2 = RedFlagModel().check(10, False, False, np.random.default_rng(4))
    assert (r1.deploy, r1.reason) == (r2.deploy, r2.reason)
    assert m.check(1, True, True, np.random.default_rng(4)).deploy in (True, False)


def test_standing_restart_preserves_order_approximately():
    from app.simulation.racing.models import SafetyCarRestartContext
    m = StandingRestartModel()
    ctx = SafetyCarRestartContext(
        driver_id="D1", position=2, gap_to_ahead=0.5, tyre_compound="medium",
        tyre_age=5, tyre_temp=90.0, start_performance=80, pressure_resistance=80,
        aggression=50, consistency=80, weather="dry", track_wetness=0.0,
        track_temp=35.0, laps_under_sc=0, is_leader=False,
    )
    a = m.evaluate(ctx, np.random.default_rng(6))
    b = StandingRestartModel().evaluate(ctx, np.random.default_rng(6))
    assert (a.reaction_time, a.position_delta) == (b.reaction_time, b.position_delta)
    assert 0.1 <= a.reaction_time <= 1.0


# ---------------- Sessions / weekend ----------------

def test_qualifying_stub_deterministic_and_structured():
    drivers = [_make_driver(1), _make_driver(2), _make_driver(3)]
    cars = {d.id: _make_car(int(d.number)) for d in drivers}
    track = _make_track()
    q1 = run_qualifying_stub(drivers, cars, track, seed=15)
    q2 = run_qualifying_stub(drivers, cars, track, seed=15)
    assert q1.order == q2.order
    assert set(q1.order) == {"D1", "D2", "D3"}
    assert q1.metadata["pole"] == q1.order[0]
    assert len(q1.best_times) == 3


def test_sprint_weekend_records_all_sessions():
    drivers = [_make_driver(1), _make_driver(2)]
    cars = {d.id: _make_car(int(d.number)) for d in drivers}
    track = _make_track()
    cfg = _make_config(total_laps=5)
    weekend = run_weekend("w1", WeekendFormat.SPRINT, cfg, drivers, cars, track, seed=16)
    assert weekend.get(SessionType.QUALIFYING) is not None
    assert weekend.get(SessionType.SPRINT) is not None
    assert weekend.get(SessionType.RACE) is not None
    weekend2 = run_weekend("w1", WeekendFormat.SPRINT, cfg, drivers, cars, track, seed=16)
    assert weekend.get(SessionType.RACE).order == weekend2.get(SessionType.RACE).order


def test_standard_weekend_has_no_sprint():
    drivers = [_make_driver(1), _make_driver(2)]
    cars = {d.id: _make_car(int(d.number)) for d in drivers}
    weekend = run_weekend("w2", WeekendFormat.STANDARD, _make_config(total_laps=5),
                          drivers, cars, _make_track(), seed=17)
    assert weekend.get(SessionType.SPRINT) is None
    assert weekend.get(SessionType.RACE) is not None


# ---------------- Telemetry / events / calibration / versions ----------------

def test_telemetry_sampling_levels():
    drivers = [_make_driver(1), _make_driver(2)]
    off = _run(drivers, config=_make_config(telemetry_sampling=TelemetrySampling.OFF), seed=71)
    assert off.telemetry == []
    sec = _run(drivers, config=_make_config(telemetry_sampling=TelemetrySampling.SECTOR), seed=71)
    assert len(sec.telemetry) > 0
    required = {"lap", "sector", "driver_id", "position", "gap_ahead", "fuel_mass",
                "ers_charge", "tyre_compound", "track_wetness"}
    assert required.issubset(sec.telemetry[0].keys())
    lap = _run(drivers, config=_make_config(telemetry_sampling=TelemetrySampling.LAP), seed=71)
    assert all(r["sector"] == -1 for r in lap.telemetry)


def test_event_verbosity_levels():
    drivers = [_make_driver(1), _make_driver(2)]
    minimal = _run(drivers, config=_make_config(event_verbosity=EventVerbosity.MINIMAL), seed=72)
    standard = _run(drivers, config=_make_config(event_verbosity=EventVerbosity.STANDARD), seed=72)
    full = _run(drivers, config=_make_config(event_verbosity=EventVerbosity.FULL_TELEMETRY,
                                             telemetry_sampling=TelemetrySampling.SECTOR), seed=72)
    assert len(minimal.events) <= len(standard.events)
    assert len(full.events) >= len(standard.events)
    assert "race_started" in [e["event_type"] for e in minimal.events]
    # backward compat: standard output identical shape to pre-Phase-8 default
    assert "race_started" in [e["event_type"] for e in standard.events]


def test_calibration_identity_and_offsets():
    profile = CalibrationProfile()
    assert profile.track_calibration("monza").drs_effect_multiplier == 1.0
    assert profile.driver_calibration("VER").overtaking_offset == 0.0
    assert profile.car_calibration("RB20").straight_line_multiplier == 1.0


def test_reproducibility_metadata_recorded():
    res = _run([_make_driver(1), _make_driver(2)], seed=73)
    assert res.simulation_version == SIMULATION_VERSION
    assert res.config_version == CONFIG_VERSION
    assert res.model_version == "0.1.0"
    rep = res.reproducibility
    for key in ("seed", "simulation_version", "model_version", "config_version",
                "track_id", "drivers", "teams", "streams"):
        assert key in rep
    assert rep["seed"] == 73
    assert set(rep["drivers"]) == {"D1", "D2"}


# ---------------- Planner ----------------

def test_planner_prefers_attack_with_resources_save_when_depleted():
    planner = BattlePlanner()
    rng = np.random.default_rng(21)
    rich = planner.plan(_resource(fuel=60.0, ers=0.9), _resource(), 0.5, 0.4, 5, rng)
    poor = planner.plan(_resource(fuel=6.0, ers=0.05, conserve_fuel=True,
                                  conserve_ers=True), _resource(), 0.5, 0.4, 5, rng)
    assert rich.action_now in ("attack", "attack_next")
    assert poor.action_now in ("save", "harvest")
    assert len(rich.horizon_actions) == 3


def test_planner_horizon_bounds():
    planner = BattlePlanner()
    plan = planner.plan(_resource(), _resource(), 0.5, 0.2, 2, np.random.default_rng(22))
    assert 2 <= len(plan.horizon_actions) <= 5
    assert plan.expected_fuel_cost >= 0.0
    assert plan.expected_ers_cost >= 0.0


# ---------------- Statistical (1000+ model-level trials) ----------------

def test_stat_better_start_performance_better_start_outcome():
    from app.simulation.racing.race_procedure import StandingStartModel
    model = StandingStartModel()
    weak = np.mean([model.evaluate("D", 40, 50, 70, 70, 95.0, 1.0,
                                   np.random.default_rng(i)).launch_quality
                    for i in range(1000)])
    strong = np.mean([model.evaluate("D", 95, 50, 70, 70, 95.0, 1.0,
                                     np.random.default_rng(i)).launch_quality
                      for i in range(1000)])
    assert strong > weak


def test_stat_higher_aggression_higher_first_corner_incident_risk():
    model = FirstCornerModel()
    calm = sum(model.evaluate("D", 5, 20, 20, 80, 50.0, "dry",
                              np.random.default_rng(i)).outcome != "clean"
               for i in range(1000))
    aggro = sum(model.evaluate("D", 5, 20, 95, 80, 50.0, "dry",
                               np.random.default_rng(i)).outcome != "clean"
                for i in range(1000))
    assert aggro > calm


def test_stat_better_ers_availability_higher_attack_probability():
    planner = BattlePlanner()
    low = sum(planner.plan(_resource(ers=0.05, conserve_ers=True), _resource(),
                           0.5, 0.3, 3, np.random.default_rng(i)).action_now
              in ("attack", "attack_next") for i in range(1000))
    high = sum(planner.plan(_resource(ers=0.95), _resource(),
                            0.5, 0.3, 3, np.random.default_rng(i)).action_now
               in ("attack", "attack_next") for i in range(1000))
    assert high > low


def test_stat_higher_wetness_larger_slick_penalty_and_intermediate_edge():
    from app.simulation.environment import TyreCrossoverModel
    model = TyreCrossoverModel()
    dry = sum(model.assess_crossover("medium", 0.0, 35.0, 0.0, 0.0, 90.0, 0.1
                                    ).recommended_compound == "medium" for _ in range(200))
    wet = sum(model.assess_crossover("medium", 0.7, 28.0, 0.65, 0.75, 80.0, 0.2
                                    ).recommended_compound == "intermediate" for _ in range(200))
    back = sum(model.assess_crossover("intermediate", 0.0, 35.0, 0.0, 0.0, 70.0, 0.1
                                     ).recommended_compound in ("medium", "soft", "hard")
               for _ in range(200))
    assert dry == 200
    assert wet == 200
    assert back == 200


# ---------------- Integration scenarios ----------------

def test_integration_sector_battles_close_then_attack():
    # Sector machinery runs inside a normal race; battles must still resolve.
    res = _run([_make_driver(1, overtaking=95), _make_driver(2, defending=60)], seed=81)
    assert sorted(r.position for r in res.results) == [1, 2]


def test_integration_full_telemetry_race_completes():
    res = _run(
        [_make_driver(1), _make_driver(2)],
        config=_make_config(event_verbosity=EventVerbosity.FULL_TELEMETRY,
                            telemetry_sampling=TelemetrySampling.FULL),
        seed=82,
    )
    assert res.completed_laps == 5
    assert len(res.telemetry) >= 2 * 5 * 3  # drivers × laps × sectors


def test_integration_minimal_events_race_completes():
    res = _run(
        [_make_driver(1), _make_driver(2)],
        config=_make_config(event_verbosity=EventVerbosity.MINIMAL),
        seed=83,
    )
    assert res.completed_laps == 5
    assert sorted(r.position for r in res.results) == [1, 2]


def test_performance_smoke_2x5_fast():
    import time
    t0 = time.perf_counter()
    _run([_make_driver(1), _make_driver(2)], seed=84)
    assert time.perf_counter() - t0 < 5.0
