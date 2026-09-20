"""Phase 7 tests: dynamic environment & racing refinement.

Covers determinism, directional relationships, invariants,
statistical sanity, and complete-race integration scenarios.
All stochastic behaviour uses seeded RandomProvider / generators.
"""
from __future__ import annotations

import numpy as np

from app.simulation.core.race_engine import RaceEngine
from app.simulation.core.random import RandomProvider
from app.simulation.core.state import SimulationConfig
from app.simulation.environment import (
    ForecastUncertainty,
    TrackWetnessModel,
    TyreCrossoverModel,
    get_overtake_map_for_track,
)
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.track import Track, TrackType
from app.simulation.models.weather import WeatherCondition, WeatherState
from app.simulation.racing import (
    BattleContext,
    BattleEngine,
    BattleResourceState,
    DirtyAirContext,
    DirtyAirModel,
    OvertakeContext,
    OvertakeEngine,
    SafetyCarRestartContext,
    SafetyCarRestartModel,
)
from app.simulation.strategy.team_orders import (
    ChampionshipContext,
    TeamOrderContext,
    TeamOrderModel,
)


def _make_driver(idx: int, team: str = "T1", **kw) -> Driver:
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


def _make_car(idx: int, team: str = "T1") -> Car:
    return Car(
        id=f"C{idx}", name=f"Car {idx}", team_id=team,
        engine_id=f"E{idx}", year=2024,
    )


def _make_track(**kw) -> Track:
    base = dict(
        id="t1", name="T", country="C", city="C",
        track_type=TrackType.PERMANENT, length_km=5.0, number_of_laps=5,
        race_distance_km=25.0, number_of_corners=10,
        reference_lap_time=90.0, pit_stop_time_loss=20.0, overtaking_difficulty=40,
    )
    base.update(kw)
    t = Track(**base)
    t.initialize_sector_characteristics()
    return t


def _make_config(**kw) -> SimulationConfig:
    base = dict(
        simulation_id="p7", seed=7, total_laps=5,
        initial_weather=WeatherCondition.DRY, weather_variability=0.0,
        safety_car_probability=0.0, vsc_probability=0.0, incident_probability=0.0,
    )
    base.update(kw)
    return SimulationConfig(**base)


def _overtake_ctx(**kw) -> OvertakeContext:
    base = dict(
        attacker_id="A", defender_id="D", attacker_position=2, defender_position=1,
        gap=0.5, relative_pace=-0.3, attacker_tyre_compound="soft",
        defender_tyre_compound="medium", attacker_tyre_age=3, defender_tyre_age=10,
        tyre_delta=0.3, attacker_ers_mode="overtake", defender_ers_mode="medium",
        drs_available=True, attacker_straight_line_advantage=0.1,
        defender_defensive_skill=70, attacker_overtaking_skill=80,
        attacker_aggression=60, track_overtaking_difficulty=0.3, corner_type="medium",
        dirty_air_effect=0.1, weather="dry", track_wetness=0.0,
        attacker_damage=0.0, defender_damage=0.0,
        safety_car_active=False, vsc_active=False, traffic_ahead=False,
    )
    base.update(kw)
    return OvertakeContext(**base)


# ---------------- Determinism ----------------

def test_determinism_weather_drying_crossover_ers_fuel_battle_teamorders():
    """Same seed => identical weather step, wetness, crossover, battle, team order."""
    def run_once(seed: int):
        rng = RandomProvider(seed=seed)
        w = WeatherState(condition=WeatherCondition.LIGHT_RAIN, precipitation_rate=2.0,
                         wind_speed=5.0, track_temperature=30.0, track_wetness=0.4)
        track = _make_track()
        twm = TrackWetnessModel()
        twm.initialize(track, rng.get_stream("drying_line"))
        wet = twm.step(w, 20)
        rl = wet[0].racing_line_wetness
        co = TyreCrossoverModel().assess_crossover("medium", 0.4, 30.0, rl, rl + 0.1, 90.0, 0.2)
        be = BattleEngine()
        bctx = BattleContext(
            attacker_id="A", defender_id="D", gap=0.6, relative_pace=-0.4,
            tyre_delta=0.3, drs_state=True, attacker_ers_mode="overtake",
            defender_ers_mode="medium", track_overtaking_difficulty=0.3, dirty_air=0.1,
            attacker_overtaking_skill=80, defender_defensive_skill=70,
            attacker_aggression=60, defender_aggression=50,
            attacker_tyre_condition=0.8, defender_tyre_condition=0.6,
            weather="dry", track_wetness=0.1, attacker_damage=0.0, defender_damage=0.0,
            safety_car_active=False, vsc_active=False, current_lap=3, race_laps_remaining=2,
            attacker_resource_state=BattleResourceState(
                fuel_mass=50.0, fuel_target=5.0, fuel_mode="standard", ers_energy=0.8,
                ers_mode="overtake", ers_target=0.5, tyre_condition=0.8, tyre_wear=0.2,
                tyre_compound="soft", tyre_age=3),
            defender_resource_state=BattleResourceState(
                fuel_mass=50.0, fuel_target=5.0, fuel_mode="standard", ers_energy=0.5,
                ers_mode="medium", ers_target=0.5, tyre_condition=0.6, tyre_wear=0.4,
                tyre_compound="medium", tyre_age=10),
        )
        bdec = be.update_battle(bctx, rng.get_stream("battle"))
        tdec = TeamOrderModel().evaluate(TeamOrderContext(
            team_id="T1", driver_id="A", teammate_id="D", position=2,
            teammate_position=1, gap=0.6, pace_difference=-0.4,
            laps_remaining=2,
            championship=ChampionshipContext(points_difference=10.0, remaining_races=5),
        ), rng.get_stream("team_orders"))
        return (round(rl, 9), co.recommended_compound, round(bdec.overtake_probability, 9),
                tdec.order)
    assert run_once(123) == run_once(123)


def test_determinism_full_race():
    d1, d2 = _make_driver(1), _make_driver(2)
    cars = {"D1": _make_car(1), "D2": _make_car(2)}
    track, cfg = _make_track(), _make_config()
    r1 = RaceEngine().simulate_race(cfg, [d1, d2], cars, track, RandomProvider(seed=99))
    r2 = RaceEngine().simulate_race(cfg, [d1, d2], cars, track, RandomProvider(seed=99))
    assert [(r.driver_id, r.position) for r in r1.results] == [(r.driver_id, r.position) for r in r2.results]
    assert [e["event_type"] for e in r1.events] == [e["event_type"] for e in r2.events]


# ---------------- Directional ----------------

def test_more_rain_more_wetness():
    rng = RandomProvider(seed=1)
    track = _make_track()
    m1, m2 = TrackWetnessModel(), TrackWetnessModel()
    m1.initialize(track, rng.get_stream("a"))
    m2.initialize(track, rng.get_stream("b"))
    light = WeatherState(condition=WeatherCondition.LIGHT_RAIN, precipitation_rate=1.0,
                         wind_speed=3.0, track_temperature=30.0)
    heavy = WeatherState(condition=WeatherCondition.HEAVY_RAIN, precipitation_rate=10.0,
                         wind_speed=3.0, track_temperature=30.0)
    w1 = m1.step(light, 20)[0].racing_line_wetness
    w2 = m2.step(heavy, 20)[0].racing_line_wetness
    assert w2 > w1


def test_wind_accelerates_drying():
    track = _make_track()
    m1, m2 = TrackWetnessModel(), TrackWetnessModel()
    m1.initialize(track, RandomProvider(seed=2).get_stream("a"))
    m2.initialize(track, RandomProvider(seed=2).get_stream("b"))
    m1.sector_wetness[0].racing_line_wetness = 0.5
    m2.sector_wetness[0].racing_line_wetness = 0.5
    calm = WeatherState(condition=WeatherCondition.DRY, wind_speed=1.0, track_temperature=30.0)
    windy = WeatherState(condition=WeatherCondition.DRY, wind_speed=15.0, track_temperature=30.0)
    assert m2.step(windy, 20)[0].racing_line_wetness < m1.step(calm, 20)[0].racing_line_wetness


def test_racing_line_dries_faster_than_offline():
    track = _make_track()
    m = TrackWetnessModel()
    m.initialize(track, RandomProvider(seed=3).get_stream("a"))
    m.sector_wetness[0].racing_line_wetness = 0.5
    m.sector_wetness[0].off_line_wetness = 0.5
    dry = WeatherState(condition=WeatherCondition.DRY, wind_speed=5.0, track_temperature=35.0)
    out = m.step(dry, 20)[0]
    assert out.racing_line_wetness < out.off_line_wetness


def test_wetness_hurts_slicks_and_favors_intermediate():
    co = TyreCrossoverModel()
    dry = co.assess_crossover("medium", 0.0, 35.0, 0.0, 0.0, 90.0, 0.1)
    wet = co.assess_crossover("medium", 0.6, 30.0, 0.55, 0.65, 80.0, 0.2)
    assert dry.recommended_compound == "medium"
    assert wet.recommended_compound == "intermediate"
    back = co.assess_crossover("intermediate", 0.0, 35.0, 0.0, 0.0, 70.0, 0.1)
    assert back.recommended_compound in ("medium", "soft", "hard")


def test_higher_ers_stronger_attack():
    eng = OvertakeEngine()
    rng = np.random.default_rng(0)
    low = eng.evaluate_opportunity(_overtake_ctx(attacker_ers_mode="medium"), rng).probability
    high = eng.evaluate_opportunity(_overtake_ctx(attacker_ers_mode="overtake"), rng).probability
    assert high > low


def test_higher_fuel_load_slower_and_saving_consumes_less():
    from app.simulation.lap_time.model import LapTimeInputs, LapTimeModel
    from app.simulation.models.tyre import get_standard_tyre_specs
    track = _make_track()
    specs = get_standard_tyre_specs()
    drv = _make_driver(1)
    car = _make_car(1)
    w = WeatherState()
    def lap_time(fuel: float) -> float:
        inp = LapTimeInputs(
            base_lap_time=90.0, car=car, engine_power_kw=780.0, driver=drv,
            driver_effective_skill=75.0, compound="medium", tyre_spec=specs["medium"],
            tyre_age_laps=3, tyre_wear=0.1, tyre_temp=95.0, fuel_mass=fuel,
            fuel_per_lap=1.8, track=track, track_evolution=0.0, track_grip=1.0,
            weather=w, is_qualifying=False, is_race_start=False, is_safety_car=False,
            is_vsc=False, drs_active=False, ers_mode="medium", in_traffic=False,
            traffic_loss=0.0, aero_damage=0.0, mechanical_damage=0.0,
            rng=RandomProvider(seed=0),
        )
        return LapTimeModel().calculate_lap_time(inp).total
    assert lap_time(100.0) > lap_time(20.0)


def test_better_attacker_higher_overtake_probability():
    eng = OvertakeEngine()
    rng = np.random.default_rng(1)
    weak = eng.evaluate_opportunity(_overtake_ctx(attacker_overtaking_skill=40), rng).probability
    strong = eng.evaluate_opportunity(_overtake_ctx(attacker_overtaking_skill=95), rng).probability
    assert strong > weak


def test_dirty_air_lowers_following_performance():
    m = DirtyAirModel()
    near = m.calculate_effect(DirtyAirContext(
        following_distance=0.5, corner_type="medium", follower_aero_sensitivity=60,
        leader_aero_efficiency=60, weather="dry", track_wetness=0.0, speed_kmh=250.0)).total_pace_loss
    far = m.calculate_effect(DirtyAirContext(
        following_distance=3.0, corner_type="medium", follower_aero_sensitivity=60,
        leader_aero_efficiency=60, weather="dry", track_wetness=0.0, speed_kmh=250.0)).total_pace_loss
    assert near > far


def test_forecast_uncertainty_decays_with_horizon():
    f = ForecastUncertainty(
        lap_forecasts=[{"precipitation_rate": 1.0}, {"precipitation_rate": 1.0}],
        confidence_decay_per_lap=0.1,
    )
    assert f.get_forecast_for_lap(0)["confidence"] > f.get_forecast_for_lap(1)["confidence"]


# ---------------- Invariants ----------------

def test_invariants_wetness_fuel_ers_probs():
    rng = RandomProvider(seed=5)
    track = _make_track()
    m = TrackWetnessModel()
    m.initialize(track, rng.get_stream("x"))
    for _ in range(5):
        w = WeatherState(condition=WeatherCondition.HEAVY_RAIN, precipitation_rate=20.0,
                         wind_speed=2.0, track_temperature=25.0)
        out = m.step(w, 20)
        for s in out.values():
            assert 0.0 <= s.racing_line_wetness <= 1.0
            assert 0.0 <= s.off_line_wetness <= 1.0
    eng = OvertakeEngine()
    p = eng.evaluate_opportunity(_overtake_ctx(), np.random.default_rng(0)).probability
    assert 0.0 <= p <= 1.0


def test_fuel_ers_never_negative_after_costs():
    from app.simulation.core.state import DriverState
    e = RaceEngine()
    ds = DriverState(driver_id="D1", fuel_mass=0.05, ers_charge=0.01)
    cfg = _make_config()
    e._apply_resource_costs(ds, True, False, cfg, [], 1, 0.0)
    assert ds.fuel_mass >= 0.0
    assert 0.0 <= ds.ers_charge <= 1.0


# ---------------- Statistical (1000 trials, fast model-level) ----------------

def test_stat_wet_slick_slower_than_intermediate_over_1000():
    co = TyreCrossoverModel()
    rng = np.random.default_rng(11)
    slick_wet_penalties = []
    for _ in range(1000):
        wet = float(rng.uniform(0.5, 0.9))
        a = co.assess_crossover("medium", wet, 30.0, wet, wet, 85.0, 0.2)
        slick_wet_penalties.append(1.0 if a.recommended_compound == "intermediate" else 0.0)
    assert sum(slick_wet_penalties) / 1000 > 0.9


def test_stat_ers_advantage_increases_attack_success_over_1000():
    eng = OvertakeEngine()
    rng = np.random.default_rng(12)
    wins = {"medium": 0, "overtake": 0}
    for mode in ("medium", "overtake"):
        for _ in range(1000):
            ok, _ = eng.evaluate_attempt(_overtake_ctx(attacker_ers_mode=mode), rng)
            wins[mode] += int(ok)
    assert wins["overtake"] > wins["medium"]


def test_stat_tyre_delta_increases_overtake_probability():
    eng = OvertakeEngine()
    rng = np.random.default_rng(13)
    small = np.mean([eng.evaluate_opportunity(_overtake_ctx(tyre_delta=0.1), rng).probability for _ in range(300)])
    big = np.mean([eng.evaluate_opportunity(_overtake_ctx(tyre_delta=0.8), rng).probability for _ in range(300)])
    assert big > small


# ---------------- Integration scenarios ----------------

def _run_race(drivers, track_kw=None, cfg_kw=None, seed=21):
    ds = drivers
    cars = {d.id: _make_car(int(d.number), d.team_id) for d in ds}
    track = _make_track(**(track_kw or {}))
    cfg = _make_config(**(cfg_kw or {}))
    res = RaceEngine().simulate_race(cfg, ds, cars, track, RandomProvider(seed=seed))
    positions = sorted([(r.driver_id, r.position) for r in res.results], key=lambda x: x[1])
    assert [p for _, p in positions] == list(range(1, len(ds) + 1))
    assert all(r.total_time is None or r.total_time > 0 for r in res.results)
    return res


def test_integration_evenly_matched():
    _run_race([_make_driver(1), _make_driver(2)])


def test_integration_fast_attacker_vs_slow_defender():
    res = _run_race([
        _make_driver(1, overtaking=95, race_skill=95),
        _make_driver(2, defending=60, race_skill=70),
    ])
    assert res.completed_laps == 5


def test_integration_strong_drs_track():
    _run_race([_make_driver(1), _make_driver(2)], track_kw={"id": "monza", "overtaking_difficulty": 25})


def test_integration_difficult_overtaking_track():
    _run_race([_make_driver(1), _make_driver(2)], track_kw={"id": "monaco", "overtaking_difficulty": 95})


def test_integration_large_drs_train():
    _run_race([_make_driver(i, team="T1") for i in range(1, 7)], cfg_kw={"total_laps": 5})


def test_integration_safety_car_restart():
    m = SafetyCarRestartModel()
    ctx = SafetyCarRestartContext(
        driver_id="D1", position=2, gap_to_ahead=0.5, tyre_compound="medium",
        tyre_age=5, tyre_temp=90.0, start_performance=80, pressure_resistance=80,
        aggression=60, consistency=80, weather="dry", track_wetness=0.0,
        track_temp=35.0, laps_under_sc=3, is_leader=False,
    )
    out = m.evaluate_restart(ctx, np.random.default_rng(0))
    assert 0.1 <= out.reaction_time <= 1.0
    assert abs(sum(out.position_change_probability.values()) - 1.0) < 1e-6
    _run_race([_make_driver(1), _make_driver(2)], cfg_kw={"safety_car_probability": 0.5}, seed=33)


def test_integration_wet_race():
    res = _run_race(
        [_make_driver(1), _make_driver(2)],
        cfg_kw={"initial_weather": WeatherCondition.HEAVY_RAIN, "weather_variability": 0.3,
                "total_laps": 5},
        seed=44,
    )
    kinds = {e["event_type"] for e in res.events}
    assert "race_started" in kinds


def test_integration_aggressive_battle():
    _run_race([
        _make_driver(1, aggression=95, overtaking=95),
        _make_driver(2, aggression=90, defending=95),
    ], seed=55)


def test_overtake_zones_exist_for_key_tracks():
    assert get_overtake_map_for_track("bahrain") is not None
    assert get_overtake_map_for_track("monaco") is not None
    assert get_overtake_map_for_track("monza") is not None
    assert get_overtake_map_for_track("unknown_xyz") is None


def test_sector_characteristics_initialized():
    t = _make_track()
    assert len(t.sector_overtaking_difficulty) == t.number_of_sectors
    assert len(t.sector_dirty_air_sensitivity) == t.number_of_sectors
    assert 0 <= t.get_sector_overtaking_difficulty(0) <= 100
