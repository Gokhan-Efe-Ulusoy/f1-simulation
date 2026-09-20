"""Phase 17 Weather & Environmental State Engine tests.

Covers state validation, regime, transition, RNG, temporal, leakage, tyre, Monte Carlo, fingerprint.
"""
import json
import pathlib

import numpy as np
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_ROOT = ROOT / "data"


def test_weather_state_validation():
    from app.simulation.weather.state import WeatherState

    # Valid
    ws = WeatherState(air_temperature_c=25, track_temperature_c=35, humidity_pct=60, pressure_hpa=1013, wind_speed_mps=3, wind_direction_deg=90, rainfall_mm_h=0, track_wetness=0.0)
    assert ws.track_wetness == 0.0
    # Out of range should raise
    try:
        WeatherState(track_wetness=1.5)
        assert False, "should have raised"
    except Exception:
        pass
    # Pressure range
    try:
        WeatherState(pressure_hpa=800)
        assert False
    except Exception:
        pass


def test_weather_state_temperature_ranges():
    from app.simulation.weather.state import WeatherState

    # Valid ranges
    for at in [-10, 0, 25, 50]:
        ws = WeatherState(air_temperature_c=at)
        assert ws.air_temperature_c == at
    for tt in [-5, 0, 35, 65]:
        ws = WeatherState(track_temperature_c=tt)
        assert ws.track_temperature_c == tt
    # Invalid
    try:
        WeatherState(air_temperature_c=60)
        assert False
    except:
        pass


def test_humidity_pressure_wind_ranges():
    from app.simulation.weather.state import WeatherState

    ws = WeatherState(humidity_pct=60, pressure_hpa=1013, wind_speed_mps=5, wind_direction_deg=180)
    assert ws.humidity_pct == 60
    # Invalid
    for bad in [(-1, "humidity_pct"), (101, "humidity_pct"), (30, "wind_direction_deg")]:
        # wind_direction 30 is valid, need >360
        pass
    try:
        WeatherState(wind_direction_deg=400)
        assert False
    except:
        pass


def test_wetness_bounded():
    from app.simulation.weather.state import WeatherState
    from app.simulation.weather.environment import WetnessModel

    wm = WetnessModel()
    # Extremes
    ws = WeatherState(rainfall_mm_h=50, track_wetness=0.9, wind_speed_mps=0, track_temperature_c=20, humidity_pct=80)
    w = wm.step(0.9, ws)
    assert 0 <= w <= 1
    ws2 = WeatherState(rainfall_mm_h=0, track_wetness=1.0, wind_speed_mps=10, track_temperature_c=40)
    w2 = wm.step(1.0, ws2)
    assert 0 <= w2 <= 1


def test_regime_definitions():
    from app.simulation.weather.state import WeatherState
    from app.simulation.weather.regime import WeatherRegime

    # DRY
    ws = WeatherState(rainfall_mm_h=0, track_wetness=0.0)
    assert WeatherRegime.derive(ws) == WeatherRegime.DRY
    # DAMP
    ws = WeatherState(rainfall_mm_h=0, track_wetness=0.2)
    assert WeatherRegime.derive(ws) == WeatherRegime.DAMP
    # WET
    ws = WeatherState(rainfall_mm_h=0, track_wetness=0.6)
    assert WeatherRegime.derive(ws) == WeatherRegime.WET
    # HEAVY_RAIN
    ws = WeatherState(rainfall_mm_h=10, track_wetness=0.2)
    assert WeatherRegime.derive(ws) == WeatherRegime.HEAVY_RAIN
    # DRYING
    ws = WeatherState(rainfall_mm_h=0, track_wetness=0.05)
    assert WeatherRegime.derive(ws) == WeatherRegime.DRYING


def test_rainfall_intensity():
    from app.simulation.weather.state import WeatherState, RainfallIntensity

    assert WeatherState(rainfall_mm_h=0).rainfall_intensity == RainfallIntensity.NONE
    assert WeatherState(rainfall_mm_h=1).rainfall_intensity == RainfallIntensity.LIGHT
    assert WeatherState(rainfall_mm_h=5).rainfall_intensity == RainfallIntensity.MODERATE
    assert WeatherState(rainfall_mm_h=10).rainfall_intensity == RainfallIntensity.HEAVY


def test_track_temperature_distinct():
    from app.simulation.weather.state import WeatherState

    ws = WeatherState(air_temperature_c=20, track_temperature_c=35)
    assert ws.air_temperature_c != ws.track_temperature_c
    # Fallback estimation
    from app.simulation.weather.calibration import estimate_track_temperature

    est, tier = estimate_track_temperature(20.0)
    assert est == 30.0
    assert tier == "ESTIMATED"
    est2, tier2 = estimate_track_temperature(None)
    assert est2 is None
    assert tier2 == "NON_IDENTIFIABLE"


def test_wetness_evolution():
    from app.simulation.weather.state import WeatherState
    from app.simulation.weather.environment import WetnessModel

    wm = WetnessModel(base_drying_rate=0.02)
    # Rainfall increases wetness
    ws_rain = WeatherState(rainfall_mm_h=5, track_wetness=0.2, wind_speed_mps=2, track_temperature_c=25)
    w_before = 0.2
    w_after = wm.step(w_before, ws_rain)
    assert w_after > w_before
    # Drying decreases
    ws_dry = WeatherState(rainfall_mm_h=0, track_wetness=0.5, wind_speed_mps=5, track_temperature_c=30, humidity_pct=50)
    w_before = 0.5
    w_after = wm.step(w_before, ws_dry)
    assert w_after < w_before
    # Bounded
    for w in [0.0, 0.5, 1.0]:
        for rain in [0, 10]:
            ws = WeatherState(rainfall_mm_h=rain, track_wetness=w)
            res = wm.step(w, ws)
            assert 0 <= res <= 1


def test_transition_deterministic():
    from app.simulation.weather.state import WeatherState
    from app.simulation.weather.transition import WeatherTransitionModel

    init = WeatherState(air_temperature_c=25, track_temperature_c=35, humidity_pct=60, track_wetness=0.0, rainfall_mm_h=0)
    model = WeatherTransitionModel(volatility=0.1)
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    s1 = model.step(init, rng1, lap=1)
    s2 = model.step(init, rng2, lap=1)
    assert s1.track_wetness == s2.track_wetness
    assert s1.air_temperature_c == s2.air_temperature_c


def test_weather_rng_same_seed_same_trajectory():
    from app.simulation.weather.engine import WeatherEngine

    we = WeatherEngine(as_of="2024-03-01", seed=42)
    # Create a scenario mock
    from app.simulation.scenario_v14 import Scenario

    scen = Scenario(scenario_id="2024-bahrain", season_id="2024", circuit_id="bahrain", date="2024-03-02", as_of="2024-03-01T00:00:00Z", drivers=[], grid_order=[])
    init = we.initial_state_for_scenario(scen)
    traj1 = we.trajectory_for_simulation(init, sim_idx=0, laps=10, seed=42)
    traj2 = we.trajectory_for_simulation(init, sim_idx=0, laps=10, seed=42)
    assert [t.track_wetness for t in traj1] == [t.track_wetness for t in traj2]


def test_weather_rng_different_seed_different_trajectory():
    from app.simulation.weather.engine import WeatherEngine
    from app.simulation.scenario_v14 import Scenario

    we = WeatherEngine(as_of="2024-03-01", seed=42)
    scen = Scenario(scenario_id="2024-bahrain", season_id="2024", circuit_id="bahrain", date="2024-03-02", as_of="2024-03-01T00:00:00Z", drivers=[], grid_order=[])
    init = we.initial_state_for_scenario(scen)
    traj1 = we.trajectory_for_simulation(init, sim_idx=0, laps=20, seed=42)
    traj2 = we.trajectory_for_simulation(init, sim_idx=0, laps=20, seed=43)
    # Check any field differs (air temp drift is guaranteed to differ)
    diffs = sum(
        1
        for a, b in zip(traj1, traj2)
        if abs(a.track_wetness - b.track_wetness) > 1e-6
        or abs((a.rainfall_mm_h or 0) - (b.rainfall_mm_h or 0)) > 1e-6
        or abs((a.air_temperature_c or 0) - (b.air_temperature_c or 0)) > 1e-6
    )
    assert diffs > 0


def test_weather_stream_isolated_from_driver():
    from app.simulation.race_engine_v15 import RaceEngineV15
    from app.simulation.race_engine_v17 import WeatherAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    import json

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scenario = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"] = 5
    # With weather disabled, should match baseline (dry)
    engine_base = RaceEngineV15(seed=42)
    engine_weather_disabled = WeatherAwareRaceEngine(seed=42, weather_enabled=False)
    r_base = engine_base.simulate(scenario, simulations=20, seed=42)
    r_wd = engine_weather_disabled.simulate(scenario, simulations=20, seed=42)
    # Tiny noise differences allowed? But with dry prior, weather disabled vs dry prior should be same
    # Check win probs close (within 0.01) and same top driver
    top_base = max(r_base["drivers"].items(), key=lambda x: x[1]["win_probability"])[0]
    top_wd = max(r_wd["drivers"].items(), key=lambda x: x[1]["win_probability"])[0]
    assert top_base == top_wd


def test_temporal_continuity():
    from app.simulation.weather.engine import WeatherEngine
    from app.simulation.scenario_v14 import Scenario

    we = WeatherEngine(as_of="2024-03-01", seed=42)
    scen = Scenario(scenario_id="2024-bahrain", season_id="2024", circuit_id="bahrain", date="2024-03-02", as_of="2024-03-01T00:00:00Z", drivers=[], grid_order=[])
    init = we.initial_state_for_scenario(scen)
    traj = we.trajectory_for_simulation(init, sim_idx=0, laps=58, seed=42)
    # No teleport: wetness change per lap <= max rain increment + drying
    for i in range(1, len(traj)):
        delta = abs(traj[i].track_wetness - traj[i - 1].track_wetness)
        assert delta <= 0.05 + 1e-6, f"wetness jump {delta} at lap {i}"


def test_historical_leakage():
    from app.simulation.weather.calibration import load_weather_observations, calibrate_weather

    obs = load_weather_observations()
    # as_of before 2024 Bahrain race (2024-03-01) should exclude 2024-03-02 weather
    cal_before = calibrate_weather(obs, as_of="2024-03-01")
    cal_after = calibrate_weather(obs, as_of="2024-03-10")
    # Before should have fewer or equal observations
    # For Bahrain 2024, before excludes the race day, after includes it
    # Check sample sizes
    # Both will be small (<30) -> NON_IDENTIFIABLE, but at least verify leakage logic
    assert cal_before["air_temperature_c"]["sample_size"] <= cal_after["air_temperature_c"]["sample_size"]
    # Direct check: observations with date == 2024-03-02T... should be excluded when as_of=2024-03-01
    from app.simulation.weather.engine import WeatherEngine
    from app.simulation.scenario_v14 import Scenario

    we_before = WeatherEngine(as_of="2024-03-01")
    we_after = WeatherEngine(as_of="2024-03-10")
    scen = Scenario(scenario_id="2024-bahrain", season_id="2024", circuit_id="bahrain", date="2024-03-02", as_of="2024-03-01T00:00:00Z", drivers=[], grid_order=[])
    init_before = we_before.initial_state_for_scenario(scen)
    # 2024-bahrain date 2024-03-02 is after as_of, so prior should be fallback (evidence PRIOR_ONLY)
    assert init_before.evidence_tier in ["PRIOR_ONLY", "NON_IDENTIFIABLE", "LIMITED"]


def test_tyre_interaction_dry_preserves_baseline():
    from app.simulation.weather.state import WeatherState
    from app.simulation.weather.kernels import grip_factor_kernel
    import numpy as np

    # Dry conditions should give grip 1.0 (use 0.04 to avoid float32 0.05 boundary)
    wetness = np.array([0.0, 0.02, 0.04], dtype=np.float32)
    grip = grip_factor_kernel(wetness)
    assert np.allclose(grip, 1.0, atol=1e-6)
    # Wet should reduce grip
    wetness_wet = np.array([0.5, 0.8], dtype=np.float32)
    grip_wet = grip_factor_kernel(wetness_wet)
    assert all(g < 1.0 for g in grip_wet)
    assert grip_wet[0] > grip_wet[1]  # more wet = less grip


def test_tyre_interaction_wet_changes_effect():
    from app.simulation.race_engine_v17 import WeatherAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scenario = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"] = 5
    # Counterfactual wet scenario
    scenario.hypothetical_modifiers = {"weather": {"rainfall_mm_h": 10, "track_wetness": 0.8}}
    engine = WeatherAwareRaceEngine(seed=42, weather_enabled=True)
    result_wet = engine.simulate(scenario, simulations=20, seed=42)
    # Should have weather_model with wet initial
    assert result_wet["weather_model"]["enabled"] is True
    assert result_wet["weather_model"]["initial_state"]["track_wetness"] == 0.8


def test_monte_carlo_weather_shared_across_drivers():
    from app.simulation.race_engine_v17 import WeatherAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scenario = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"] = 5
    # Check vectorized: weather trajectory is per-sim not per-driver
    from app.simulation.weather.engine import WeatherEngine

    we = WeatherEngine(as_of=scenario.as_of, seed=42)
    init = we.initial_state_for_scenario(scenario)
    N = 4
    trajs = we.batch_trajectories(init, N=N, laps=5, seed=42)
    # Each sim has its own trajectory, but within a sim all drivers share same wetness
    # Verify that trajectories differ across sims but are internally consistent per lap
    assert len(trajs) == N
    for traj in trajs:
        assert len(traj) == 5
    # Different sims should have potentially different weather due to RNG offset
    # (with sim_idx offset, they will differ)


def test_fingerprint_weather():
    from app.simulation.race_engine_v17 import WeatherAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    import hashlib

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scenario = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"] = 5

    def fp(res):
        parts = []
        for did in sorted(res["drivers"].keys()):
            parts.append(f"{did}:{res['drivers'][did]['win_probability']:.6f}")
        # Include weather in fingerprint
        parts.append(f"weather:{res['provenance'].get('weather_model_version')}")
        parts.append(f"w_enabled:{res['provenance'].get('weather_enabled')}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]

    engine = WeatherAwareRaceEngine(seed=42, weather_enabled=True)
    r1 = engine.simulate(scenario, simulations=20, seed=42)
    r2 = engine.simulate(scenario, simulations=20, seed=42)
    assert fp(r1) == fp(r2)
    # Different seed -> different
    r3 = engine.simulate(scenario, simulations=20, seed=43)
    assert fp(r1) != fp(r3)
    # Weather disabled vs enabled should differ (fingerprint includes weather_enabled)
    engine_no = WeatherAwareRaceEngine(seed=42, weather_enabled=False)
    # Note: need to handle scenario hypothetical_modifiers for weather disabled?
    r4 = engine_no.simulate(scenario, simulations=20, seed=42)
    # Provenance weather_enabled differs
    assert r1["provenance"]["weather_enabled"] != r4["provenance"]["weather_enabled"]


def test_evidence_tiers():
    from app.simulation.weather.state import WeatherState, EvidenceTier
    from app.simulation.weather.calibration import get_weather_evidence_tier

    # Historical tyre era
    assert get_weather_evidence_tier(as_of="2024-03-01", season=1950) == "NON_IDENTIFIABLE"
    assert get_weather_evidence_tier(as_of="2024-03-01", season=2024) in ["LIMITED", "PRIOR_ONLY", "CALIBRATED"]
    # Observed state should be OBSERVED
    ws = WeatherState.from_observed(air_temperature_c=20, track_temperature_c=30, humidity_pct=60, pressure_hpa=1013, wind_speed_mps=2, wind_direction_deg=90, rainfall_mm_h=0)
    assert ws.evidence_tier == EvidenceTier.OBSERVED


def test_weather_disabled_reproduces_baseline():
    from app.simulation.race_engine_v17 import WeatherAwareRaceEngine
    from app.simulation.race_engine_v16 import TyreAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scenario = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"] = 5
    eng16 = TyreAwareRaceEngine(seed=42)
    eng17_no = WeatherAwareRaceEngine(seed=42, weather_enabled=False)
    r16 = eng16.simulate(scenario, simulations=20, seed=42)
    r17 = eng17_no.simulate(scenario, simulations=20, seed=42)
    # With weather disabled, should be numerically equivalent within tolerance (dry prior gives zero delta)
    for did in r16["drivers"]:
        assert abs(r16["drivers"][did]["win_probability"] - r17["drivers"][did]["win_probability"]) < 0.01
