import pytest

from app.simulation.models.tyre import (
    TyreCompound,
    TyreState,
    get_compound_for_weather,
    get_standard_tyre_specs,
)
from app.simulation.tyre.model import DEFAULT_TYRE_MODEL, TyrePhysicsInputs


class TestTyreSpec:
    """Tests for TyreSpec model."""

    def test_standard_specs_exist(self):
        specs = get_standard_tyre_specs()

        assert TyreCompound.SOFT in specs
        assert TyreCompound.MEDIUM in specs
        assert TyreCompound.HARD in specs
        assert TyreCompound.INTERMEDIATE in specs
        assert TyreCompound.WET in specs

    def test_compound_pace_order(self):
        specs = get_standard_tyre_specs()

        # Soft < Medium < Hard < Intermediate < Wet (pace factor)
        assert specs[TyreCompound.SOFT].base_pace_factor < specs[TyreCompound.MEDIUM].base_pace_factor
        assert specs[TyreCompound.MEDIUM].base_pace_factor < specs[TyreCompound.HARD].base_pace_factor
        assert specs[TyreCompound.HARD].base_pace_factor < specs[TyreCompound.INTERMEDIATE].base_pace_factor
        assert specs[TyreCompound.INTERMEDIATE].base_pace_factor < specs[TyreCompound.WET].base_pace_factor

    def test_compound_degradation_order(self):
        specs = get_standard_tyre_specs()

        # Soft degrades fastest, Hard slowest
        assert specs[TyreCompound.SOFT].degradation_rate > specs[TyreCompound.MEDIUM].degradation_rate
        assert specs[TyreCompound.MEDIUM].degradation_rate > specs[TyreCompound.HARD].degradation_rate

    def test_compound_max_life_order(self):
        specs = get_standard_tyre_specs()

        # Hard lasts longest, Soft shortest
        assert specs[TyreCompound.HARD].max_life_laps > specs[TyreCompound.MEDIUM].max_life_laps
        assert specs[TyreCompound.MEDIUM].max_life_laps > specs[TyreCompound.SOFT].max_life_laps

    def test_weather_suitability(self):
        specs = get_standard_tyre_specs()

        # Dry weather
        assert specs[TyreCompound.SOFT].get_weather_suitability("dry") == 1.0
        assert specs[TyreCompound.MEDIUM].get_weather_suitability("dry") == 1.0
        assert specs[TyreCompound.WET].get_weather_suitability("dry") == 0.0

        # Wet weather
        assert specs[TyreCompound.WET].get_weather_suitability("heavy_rain") == 1.0
        assert specs[TyreCompound.INTERMEDIATE].get_weather_suitability("light_rain") == 0.7
        assert specs[TyreCompound.SOFT].get_weather_suitability("wet") == 0.0

    def test_pace_factor_increases_with_age(self):
        spec = get_standard_tyre_specs()[TyreCompound.MEDIUM]

        pace_new = spec.get_pace_factor(age_laps=1, wear=0.0, temp=90)
        pace_old = spec.get_pace_factor(age_laps=20, wear=0.5, temp=90)

        assert pace_old > pace_new  # Older tyres = slower

    def test_pace_factor_worse_when_cold(self):
        spec = get_standard_tyre_specs()[TyreCompound.MEDIUM]

        pace_optimal = spec.get_pace_factor(age_laps=5, wear=0.1, temp=95)
        pace_cold = spec.get_pace_factor(age_laps=5, wear=0.1, temp=60)

        assert pace_cold > pace_optimal

    def test_pace_factor_worse_when_overheating(self):
        spec = get_standard_tyre_specs()[TyreCompound.MEDIUM]

        pace_optimal = spec.get_pace_factor(age_laps=5, wear=0.1, temp=95)
        pace_hot = spec.get_pace_factor(age_laps=5, wear=0.1, temp=130)

        assert pace_hot > pace_optimal

    def test_get_compound_for_weather(self):
        dry_compounds = get_compound_for_weather("dry")
        assert set(dry_compounds) == {TyreCompound.SOFT, TyreCompound.MEDIUM, TyreCompound.HARD}

        wet_compounds = get_compound_for_weather("heavy_rain")
        assert TyreCompound.WET in wet_compounds
        assert TyreCompound.INTERMEDIATE in wet_compounds

        inter_compounds = get_compound_for_weather("light_rain")
        assert TyreCompound.INTERMEDIATE in inter_compounds


class TestTyreState:
    """Tests for TyreState."""

    def test_tyre_state_creation(self):
        state = TyreState(
            compound=TyreCompound.MEDIUM,
            set_id="MED_001",
        )

        assert state.compound == TyreCompound.MEDIUM
        assert state.age_laps == 0
        assert state.wear == 0.0

    def test_avg_temp_and_pressure(self):
        state = TyreState(
            compound=TyreCompound.MEDIUM,
            set_id="MED_001",
            temp_fl=90, temp_fr=92, temp_rl=88, temp_rr=89,
            pressure_fl=22, pressure_fr=22, pressure_rl=22, pressure_rr=22,
        )

        assert state.avg_temp == 89.75
        assert state.avg_pressure == 22.0

    def test_is_worn_out(self):
        state_new = TyreState(compound=TyreCompound.MEDIUM, set_id="MED_001", wear=0.5)
        state_worn = TyreState(compound=TyreCompound.MEDIUM, set_id="MED_002", wear=1.0)

        assert not state_new.is_worn_out()
        assert state_worn.is_worn_out()

    def test_is_in_optimal_window(self):
        specs = get_standard_tyre_specs()
        spec = specs[TyreCompound.MEDIUM]

        state_optimal = TyreState(
            compound=TyreCompound.MEDIUM, set_id="MED_001",
            temp_fl=95, temp_fr=95, temp_rl=95, temp_rr=95,
        )

        state_cold = TyreState(
            compound=TyreCompound.MEDIUM, set_id="MED_002",
            temp_fl=60, temp_fr=60, temp_rl=60, temp_rr=60,
        )

        assert state_optimal.is_in_optimal_window(spec)
        assert not state_cold.is_in_optimal_window(spec)

    def test_get_grip_level(self):
        specs = get_standard_tyre_specs()
        spec = specs[TyreCompound.MEDIUM]

        state_new = TyreState(
            compound=TyreCompound.MEDIUM, set_id="MED_001",
            wear=0.0, temp_fl=95, temp_fr=95, temp_rl=95, temp_rr=95,
        )

        state_old = TyreState(
            compound=TyreCompound.MEDIUM, set_id="MED_002",
            wear=0.8, temp_fl=95, temp_fr=95, temp_rl=95, temp_rr=95,
        )

        grip_new = state_new.get_grip_level(spec)
        grip_old = state_old.get_grip_level(spec)

        assert grip_new > grip_old
        assert grip_new <= spec.peak_grip


class TestTyreModel:
    """Tests for TyreModel physics."""

    def test_temperature_update(self):
        from app.simulation.core.random import RandomProvider
        from app.simulation.models.car import Car
        from app.simulation.models.track import Track
        from app.simulation.models.weather import WeatherState

        specs = get_standard_tyre_specs()
        spec = specs[TyreCompound.MEDIUM]

        car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
        track = Track(id="TEST", name="Test", country="Test", city="Test", track_temp=35)
        weather = WeatherState(condition="dry", track_temperature=35, track_wetness=0.0)

        state = TyreState(compound=TyreCompound.MEDIUM, set_id="MED_001")

        inputs = TyrePhysicsInputs(
            compound=TyreCompound.MEDIUM,
            spec=spec,
            state=state,
            car=car,
            track=track,
            weather=weather,
            track_temp=35,
            track_wetness=0.0,
            fuel_mass=50,
            stint_lap=0,
            rng=RandomProvider(seed=42),
        )

        new_state = DEFAULT_TYRE_MODEL.step(inputs)

        # Temperature should move toward target
        assert new_state.avg_temp > state.avg_temp or new_state.avg_temp < state.avg_temp
        assert new_state.age_laps == 1
        assert new_state.wear >= state.wear

    def test_wear_increases(self):
        from app.simulation.core.random import RandomProvider
        from app.simulation.models.car import Car
        from app.simulation.models.track import Track
        from app.simulation.models.weather import WeatherState

        specs = get_standard_tyre_specs()
        spec = specs[TyreCompound.SOFT]

        car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
        track = Track(id="TEST", name="Test", country="Test", city="Test")
        weather = WeatherState(condition="dry")

        state = TyreState(compound=TyreCompound.SOFT, set_id="SOFT_001")

        inputs = TyrePhysicsInputs(
            compound=TyreCompound.SOFT,
            spec=spec,
            state=state,
            car=car,
            track=track,
            weather=weather,
            track_temp=35,
            track_wetness=0.0,
            fuel_mass=50,
            stint_lap=0,
            rng=RandomProvider(seed=42),
        )

        # Simulate multiple laps
        for i in range(10):
            inputs.state = state
            inputs.stint_lap = i
            state = DEFAULT_TYRE_MODEL.step(inputs)

        assert state.wear > 0
        assert state.age_laps == 10

    def test_wear_faster_when_pushing(self):
        from app.simulation.core.random import RandomProvider
        from app.simulation.models.car import Car
        from app.simulation.models.track import Track
        from app.simulation.models.weather import WeatherState

        specs = get_standard_tyre_specs()
        spec = specs[TyreCompound.MEDIUM]
        car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
        track = Track(id="TEST", name="Test", country="Test", city="Test")
        weather = WeatherState(condition="dry")

        # Normal driving
        state_normal = TyreState(compound=TyreCompound.MEDIUM, set_id="MED_001")
        inputs_normal = TyrePhysicsInputs(
            compound=TyreCompound.MEDIUM, spec=spec, state=state_normal,
            car=car, track=track, weather=weather,
            track_temp=35, track_wetness=0.0, fuel_mass=50,
            is_pushing=False, rng=RandomProvider(seed=42),
        )

        for i in range(10):
            inputs_normal.state = state_normal
            inputs_normal.stint_lap = i
            state_normal = DEFAULT_TYRE_MODEL.step(inputs_normal)

        # Pushing hard
        state_push = TyreState(compound=TyreCompound.MEDIUM, set_id="MED_002")
        inputs_push = TyrePhysicsInputs(
            compound=TyreCompound.MEDIUM, spec=spec, state=state_push,
            car=car, track=track, weather=weather,
            track_temp=35, track_wetness=0.0, fuel_mass=50,
            is_pushing=True, rng=RandomProvider(seed=42),
        )

        for i in range(10):
            inputs_push.state = state_push
            inputs_push.stint_lap = i
            state_push = DEFAULT_TYRE_MODEL.step(inputs_push)

        assert state_push.wear > state_normal.wear

    def test_estimate_stint_length(self):
        from app.simulation.models.car import Car
        from app.simulation.models.track import Track

        car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
        track = Track(id="TEST", name="Test", country="Test", city="Test")

        # Soft should last fewer laps than medium than hard
        soft_laps = DEFAULT_TYRE_MODEL.estimate_stint_length(TyreCompound.SOFT, car, track, 50)
        medium_laps = DEFAULT_TYRE_MODEL.estimate_stint_length(TyreCompound.MEDIUM, car, track, 50)
        hard_laps = DEFAULT_TYRE_MODEL.estimate_stint_length(TyreCompound.HARD, car, track, 50)

        assert soft_laps < medium_laps < hard_laps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
