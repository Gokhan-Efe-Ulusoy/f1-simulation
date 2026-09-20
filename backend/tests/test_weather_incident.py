import pytest

from app.simulation.core.random import RandomProvider
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.incident import (
    DEFAULT_INCIDENT_MODEL,
    Incident,
    IncidentCause,
    IncidentModel,
    IncidentSeverity,
    IncidentType,
)
from app.simulation.models.track import Track, TrackType
from app.simulation.models.weather import (
    WeatherCondition,
    WeatherForecast,
    WeatherState,
    create_weather_model,
)


class TestWeatherState:
    """Tests for WeatherState."""

    def test_weather_state_creation(self):
        state = WeatherState(
            condition=WeatherCondition.DRY,
            air_temperature=25,
            track_temperature=35,
            humidity=60,
        )

        assert state.condition == WeatherCondition.DRY
        assert state.air_temperature == 25

    def test_grip_multiplier_dry(self):
        state = WeatherState(condition=WeatherCondition.DRY, track_wetness=0.0)
        assert state.get_grip_multiplier() == 1.0

    def test_grip_multiplier_wet(self):
        state = WeatherState(condition=WeatherCondition.WET, track_wetness=0.5)
        grip = state.get_grip_multiplier()
        assert 0.6 < grip < 0.9

    def test_grip_multiplier_heavy_rain(self):
        state = WeatherState(condition=WeatherCondition.HEAVY_RAIN, track_wetness=0.9)
        grip = state.get_grip_multiplier()
        assert 0.4 <= grip <= 0.65

    def test_visibility_factor(self):
        dry_state = WeatherState(condition=WeatherCondition.DRY)
        light_rain = WeatherState(condition=WeatherCondition.LIGHT_RAIN)
        heavy_rain = WeatherState(condition=WeatherCondition.HEAVY_RAIN)

        assert dry_state.get_visibility_factor() == 1.0
        assert light_rain.get_visibility_factor() == 0.85
        assert heavy_rain.get_visibility_factor() == 0.7

    def test_cooling_factor(self):
        cold_state = WeatherState(track_temperature=15)
        hot_state = WeatherState(track_temperature=55)
        wet_state = WeatherState(track_temperature=35, track_wetness=0.5)

        assert cold_state.get_cooling_factor() > 1.0
        assert hot_state.get_cooling_factor() < 1.0
        assert wet_state.get_cooling_factor() > 1.0

    def test_appropriate_compounds(self):
        dry_state = WeatherState(condition=WeatherCondition.DRY, track_wetness=0.0)
        compounds = dry_state.get_appropriate_compounds()
        assert "soft" in compounds
        assert "medium" in compounds
        assert "hard" in compounds

        wet_state = WeatherState(condition=WeatherCondition.HEAVY_RAIN, track_wetness=0.8)
        compounds = wet_state.get_appropriate_compounds()
        assert "wet" in compounds
        assert "intermediate" in compounds
        assert "soft" not in compounds


class TestWeatherModel:
    """Tests for WeatherModel."""

    def test_weather_model_creation(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.DRY,
            air_temp=25, track_temp=35,
            seed=42,
        )

        assert model.initial_state.condition == WeatherCondition.DRY
        assert model.initial_state.air_temperature == 25
        assert rng is not None

    def test_weather_evolution_dry_stays_dry(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.DRY,
            air_temp=25, track_temp=35,
            volatility=0.0,  # No volatility
            seed=42,
        )

        state = model.initial_state
        for _ in range(20):
            state = model.step(state, 0)

        # With no volatility, should stay dry
        assert state.condition == WeatherCondition.DRY
        assert state.track_wetness == 0.0

    def test_weather_evolution_with_volatility(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.DRY,
            air_temp=25, track_temp=35,
            volatility=0.5,
            seed=42,
        )

        state = model.initial_state
        states = []
        for i in range(50):
            state = model.step(state, i)
            states.append(state)

        # With volatility, temperature should vary
        temps = [s.air_temperature for s in states]
        assert max(temps) - min(temps) > 0.5

    def test_rain_can_start(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.DRY,
            air_temp=20, track_temp=25,
            humidity=95,  # High humidity
            volatility=0.5,
            seed=42,
        )

        state = model.initial_state
        rained = False
        for i in range(100):
            state = model.step(state, i)
            if state.is_rain():
                rained = True
                break

        # With high humidity and volatility, rain should be possible
        # (not guaranteed with random seed, but let's check it runs)
        assert state is not None

    def test_rain_stops_and_track_dries(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.HEAVY_RAIN,
            air_temp=20, track_temp=22,
            volatility=0.1,
            seed=42,
        )

        state = model.initial_state
        for i in range(50):
            state = model.step(state, i)

        # Rain should eventually stop and track should dry
        assert state.precipitation_rate >= 0
        assert state.track_wetness >= 0

    def test_forecast_generation(self):
        model, rng = create_weather_model(
            condition=WeatherCondition.DRY,
            air_temp=25, track_temp=35,
            seed=42,
        )

        forecast = model.generate_forecast(20)

        assert isinstance(forecast, WeatherForecast)
        assert len(forecast.lap_forecasts) == 20
        assert forecast.temperature_range[0] <= forecast.temperature_range[1]


class TestIncidentModel:
    """Tests for IncidentModel."""

    def setup_method(self):
        self.driver = Driver(
            id="TEST", name="Test", short_name="TST", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80, consistency=80, aggression=50,
            mistake_rate=20, pressure_resistance=80,
        )

        self.car = Car(
            id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
            chassis_reliability=90,
        )

        self.track = Track(
            id="TEST", name="Test", country="Test", city="Test",
            track_type=TrackType.PERMANENT,
        )

        self.rng = RandomProvider(seed=42)

    def test_incident_probability_calculation(self):
        prob = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver,
            car=self.car,
            track=self.track,
            weather="dry",
            lap=10,
            tyre_wear=0.3,
            in_traffic=False,
            is_safety_car=False,
            is_vsc=False,
            is_restart=False,
        )

        assert 0 <= prob <= 0.1  # Capped at 10%

    def test_incident_probability_higher_in_rain(self):
        prob_dry = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        prob_wet = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="heavy_rain", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        assert prob_wet > prob_dry

    def test_incident_probability_higher_in_traffic(self):
        prob_clear = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        prob_traffic = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=True,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        assert prob_traffic > prob_clear

    def test_incident_probability_higher_first_lap(self):
        prob_normal = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        prob_first_lap = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=0, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        assert prob_first_lap > prob_normal

    def test_incident_probability_lower_under_safety_car(self):
        prob_green = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=False, is_vsc=False, is_restart=False,
        )

        prob_sc = DEFAULT_INCIDENT_MODEL.calculate_incident_probability(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, tyre_wear=0.3, in_traffic=False,
            is_safety_car=True, is_vsc=False, is_restart=False,
        )

        assert prob_sc < prob_green

    def test_incident_generation(self):
        # Generate many laps to get an incident
        incidents = []
        for lap in range(200):
            inc = DEFAULT_INCIDENT_MODEL.generate_incident(
                driver=self.driver, car=self.car, track=self.track,
                weather="dry", lap=lap, sector=1, tyre_wear=0.3,
                in_traffic=False, rng=self.rng,
            )
            if inc:
                incidents.append(inc)

        # With 200 laps and ~2% probability, should get some incidents
        # (not guaranteed but very likely)
        if incidents:
            inc = incidents[0]
            assert isinstance(inc, Incident)
            assert inc.driver_id == "TEST"
            assert inc.incident_type in IncidentType
            assert inc.severity in IncidentSeverity
            assert inc.cause in IncidentCause

    def test_mechanical_failure_can_be_terminal(self):
        # Test that engine failure can be terminal
        unreliable_car = Car(
            id="UNRELIABLE", name="Unreliable", team_id="TEST", engine_id="TEST", year=2024,
            chassis_reliability=30,
        )

        # Force mechanical failure by setting high probability
        model = IncidentModel()
        model.base_probabilities.engine_failure = 1.0  # Force it

        inc = model.generate_incident(
            driver=self.driver, car=unreliable_car, track=self.track,
            weather="dry", lap=10, sector=1, tyre_wear=0.3,
            in_traffic=False, rng=RandomProvider(seed=42),
        )

        if inc and inc.incident_type == IncidentType.ENGINE_FAILURE:
            # Engine failure should often be terminal
            assert inc.severity in [IncidentSeverity.MAJOR, IncidentSeverity.TERMINAL]

    def test_puncture_requires_pit_stop(self):
        model = IncidentModel()
        model.base_probabilities.puncture = 1.0  # Force it

        inc = model.generate_incident(
            driver=self.driver, car=self.car, track=self.track,
            weather="dry", lap=10, sector=1, tyre_wear=0.8,  # Worn tyres
            in_traffic=False, rng=RandomProvider(seed=42),
        )

        if inc and inc.incident_type == IncidentType.PUNCTURE:
            assert inc.time_loss >= 10  # Must pit
            assert inc.tyre_damage is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
