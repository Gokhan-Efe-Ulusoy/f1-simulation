import pytest

from app.simulation.core.random import RandomProvider
from app.simulation.lap_time.model import LapTimeInputs, LapTimeModel, calculate_lap_time
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.track import CornerType, Track
from app.simulation.models.tyre import TyreCompound, get_standard_tyre_specs
from app.simulation.models.weather import WeatherState


class TestLapTimeModel:
    """Tests for LapTimeModel."""

    def setup_method(self):
        """Create standard test fixtures."""
        # Create driver
        self.driver = Driver(
            id="VER", name="Max Verstappen", short_name="VER", number=1,
            nationality="Dutch", date_of_birth="1997-09-27", team_id="RED_BULL",
            overall_skill=95, qualifying_skill=97, race_skill=96,
            consistency=90, aggression=85, tyre_management=88,
            wet_weather_skill=92, overtaking=94, defending=93,
            start_performance=95, adaptability=90, pressure_resistance=95,
            mistake_rate=10,
        )

        # Create car
        self.car = Car(
            id="RB20", name="Red Bull RB20", team_id="RED_BULL",
            engine_id="HONDA_2024", year=2024,
            overall_downforce=85, aero_efficiency=80, mechanical_grip=82,
            traction=80, braking_stability=85, drs_effectiveness=80,
            tyre_wear_front=80, tyre_wear_rear=80, tyre_warmup_speed=85,
        )

        # Create track
        self.track = Track(
            id="bahrain", name="Bahrain International Circuit", country="Bahrain", city="Sakhir",
            track_type="permanent", length_km=5.412, number_of_laps=57,
            race_distance_km=308.238, number_of_corners=15,
            corner_distribution={
                CornerType.HAIRPIN: 2, CornerType.SLOW: 3, CornerType.MEDIUM: 4,
                CornerType.FAST: 3, CornerType.HIGH_SPEED: 2, CornerType.CHICANE: 1,
            },
            longest_straight_km=1.1, overtaking_difficulty=35,
            front_tyre_stress=60, rear_tyre_stress=55,
            base_degradation_rate=0.045, reference_lap_time=90.5,
            track_evolution_rate=0.025,
        )

        # Create tyre spec
        self.specs = get_standard_tyre_specs()
        self.tyre_spec = self.specs[TyreCompound.MEDIUM]

        # Create weather
        self.weather = WeatherState(
            condition="dry", air_temperature=25, track_temperature=35,
            track_wetness=0.0, humidity=60,
        )

        # Create model
        self.model = LapTimeModel()

    def create_inputs(self, **overrides) -> LapTimeInputs:
        """Create standard inputs with optional overrides."""
        defaults = {
            "base_lap_time": self.track.reference_lap_time,
            "car": self.car,
            "engine_power_kw": 780,
            "driver": self.driver,
            "driver_effective_skill": self.driver.get_effective_skill("bahrain", "dry", "race"),
            "compound": TyreCompound.MEDIUM,
            "tyre_spec": self.tyre_spec,
            "tyre_age_laps": 10,
            "tyre_wear": 0.3,
            "tyre_temp": 95,
            "fuel_mass": 50,
            "fuel_per_lap": 1.8,
            "track": self.track,
            "track_evolution": 0.5,
            "track_grip": 1.0,
            "weather": self.weather,
            "rng": RandomProvider(seed=42),
        }
        defaults.update(overrides)
        return LapTimeInputs(**defaults)

    def test_lap_time_calculation_returns_components(self):
        """Lap time calculation should return all components."""
        inputs = self.create_inputs()
        result = self.model.calculate_lap_time(inputs)

        assert isinstance(result.base_time, float)
        assert isinstance(result.car_delta, float)
        assert isinstance(result.driver_delta, float)
        assert isinstance(result.fuel_delta, float)
        assert isinstance(result.tyre_delta, float)
        assert isinstance(result.tyre_degradation_delta, float)
        assert isinstance(result.weather_delta, float)
        assert isinstance(result.traffic_delta, float)
        assert isinstance(result.track_evolution_delta, float)
        assert isinstance(result.drs_delta, float)
        assert isinstance(result.ers_delta, float)
        assert isinstance(result.damage_delta, float)
        assert isinstance(result.stochastic_delta, float)
        assert isinstance(result.total, float)

    def test_faster_car_gives_lower_lap_time(self):
        """Better car should produce faster lap times."""
        # Create a slower car
        slow_car = Car(
            id="SLOW", name="Slow Car", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=60, aero_efficiency=60, mechanical_grip=60,
            traction=60, braking_stability=60,
        )

        fast_inputs = self.create_inputs(car=self.car)
        slow_inputs = self.create_inputs(car=slow_car)

        fast_result = self.model.calculate_lap_time(fast_inputs)
        slow_result = self.model.calculate_lap_time(slow_inputs)

        assert fast_result.total < slow_result.total
        assert fast_result.car_delta < slow_result.car_delta

    def test_better_driver_gives_lower_lap_time(self):
        """Better driver should produce faster lap times."""
        # Create a slower driver
        slow_driver = Driver(
            id="SLOW", name="Slow", short_name="SLW", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=70, qualifying_skill=70, race_skill=70,
            consistency=70, aggression=50, tyre_management=70,
            wet_weather_skill=70, overtaking=70, defending=70,
            start_performance=70, adaptability=70, pressure_resistance=70,
            mistake_rate=30,
        )

        fast_inputs = self.create_inputs(driver=self.driver, driver_effective_skill=self.driver.get_effective_skill("bahrain", "dry", "race"))
        slow_inputs = self.create_inputs(driver=slow_driver, driver_effective_skill=slow_driver.get_effective_skill("bahrain", "dry", "race"))

        fast_result = self.model.calculate_lap_time(fast_inputs)
        slow_result = self.model.calculate_lap_time(slow_inputs)

        assert fast_result.total < slow_result.total
        assert fast_result.driver_delta < slow_result.driver_delta

    def test_worn_tyres_gives_higher_lap_time(self):
        """Worn tyres should produce slower lap times."""
        new_tyre_inputs = self.create_inputs(tyre_age_laps=1, tyre_wear=0.0)
        worn_tyre_inputs = self.create_inputs(tyre_age_laps=25, tyre_wear=0.8)

        new_result = self.model.calculate_lap_time(new_tyre_inputs)
        worn_result = self.model.calculate_lap_time(worn_tyre_inputs)

        assert worn_result.total > new_result.total
        assert worn_result.tyre_degradation_delta > new_result.tyre_degradation_delta

    def test_heavier_fuel_gives_higher_lap_time(self):
        """Heavier fuel load should produce slower lap times."""
        light_fuel_inputs = self.create_inputs(fuel_mass=10)
        heavy_fuel_inputs = self.create_inputs(fuel_mass=100)

        light_result = self.model.calculate_lap_time(light_fuel_inputs)
        heavy_result = self.model.calculate_lap_time(heavy_fuel_inputs)

        assert heavy_result.total > light_result.total
        assert heavy_result.fuel_delta > light_result.fuel_delta

    def test_rain_gives_higher_lap_time(self):
        """Rain should produce slower lap times."""
        dry_weather = WeatherState(condition="dry", track_temperature=35, track_wetness=0.0)
        wet_weather = WeatherState(condition="heavy_rain", track_temperature=25, track_wetness=0.8, precipitation_rate=10)

        dry_inputs = self.create_inputs(weather=dry_weather)
        wet_inputs = self.create_inputs(weather=wet_weather)

        dry_result = self.model.calculate_lap_time(dry_inputs)
        wet_result = self.model.calculate_lap_time(wet_inputs)

        assert wet_result.total > dry_result.total
        assert wet_result.weather_delta > dry_result.weather_delta

    def test_traffic_gives_higher_lap_time(self):
        """Traffic should produce slower lap times."""
        clear_inputs = self.create_inputs(in_traffic=False, traffic_loss=0.0)
        traffic_inputs = self.create_inputs(in_traffic=True, traffic_loss=1.5)

        clear_result = self.model.calculate_lap_time(clear_inputs)
        traffic_result = self.model.calculate_lap_time(traffic_inputs)

        assert traffic_result.total > clear_result.total
        assert traffic_result.traffic_delta > clear_result.traffic_delta

    def test_drs_reduces_lap_time(self):
        """DRS should reduce lap time."""
        no_drs_inputs = self.create_inputs(drs_active=False)
        drs_inputs = self.create_inputs(drs_active=True)

        no_drs_result = self.model.calculate_lap_time(no_drs_inputs)
        drs_result = self.model.calculate_lap_time(drs_inputs)

        assert drs_result.total < no_drs_result.total
        assert drs_result.drs_delta < 0

    def test_track_evolution_reduces_lap_time(self):
        """Track evolution should reduce lap time."""
        green_inputs = self.create_inputs(track_evolution=0.0)
        rubbered_inputs = self.create_inputs(track_evolution=1.0)

        green_result = self.model.calculate_lap_time(green_inputs)
        rubbered_result = self.model.calculate_lap_time(rubbered_inputs)

        assert rubbered_result.total < green_result.total
        assert rubbered_result.track_evolution_delta < 0

    def test_qualifying_mode_faster(self):
        """Qualifying mode should be faster (lower fuel, fresh tyres)."""
        race_inputs = self.create_inputs(
            is_qualifying=False, fuel_mass=50, tyre_age_laps=10, tyre_wear=0.3,
        )
        quali_inputs = self.create_inputs(
            is_qualifying=True, fuel_mass=10, tyre_age_laps=1, tyre_wear=0.0,
        )

        race_result = self.model.calculate_lap_time(race_inputs)
        quali_result = self.model.calculate_lap_time(quali_inputs)

        assert quali_result.total < race_result.total

    def test_deterministic_with_same_seed(self):
        """Same seed should produce identical results."""
        rng1 = RandomProvider(seed=42)
        rng2 = RandomProvider(seed=42)

        inputs1 = self.create_inputs(rng=rng1)
        inputs2 = self.create_inputs(rng=rng2)

        result1 = self.model.calculate_lap_time(inputs1)
        result2 = self.model.calculate_lap_time(inputs2)

        assert result1.total == result2.total
        assert result1.stochastic_delta == result2.stochastic_delta

    def test_minimum_lap_time_enforced(self):
        """Lap time should not go below minimum factor."""
        # Create an extremely fast scenario
        extreme_inputs = self.create_inputs(
            car=Car(id="EXTREME", name="Extreme", team_id="TEST", engine_id="TEST", year=2024,
                    overall_downforce=100, aero_efficiency=100, mechanical_grip=100,
                    traction=100, braking_stability=100),
            driver=Driver(id="EXT", name="Extreme", short_name="EXT", number=1,
                         nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
                         overall_skill=100, qualifying_skill=100, race_skill=100,
                         consistency=100, aggression=100, tyre_management=100,
                         wet_weather_skill=100, overtaking=100, defending=100,
                         start_performance=100, adaptability=100, pressure_resistance=100,
                         mistake_rate=0),
            driver_effective_skill=100,
            tyre_age_laps=1, tyre_wear=0.0, tyre_temp=95,
            fuel_mass=5, track_evolution=1.5, drs_active=True,
            track_grip=1.0,
        )

        result = self.model.calculate_lap_time(extreme_inputs)
        min_time = extreme_inputs.base_lap_time * self.model.min_lap_time_factor

        assert result.total >= min_time


class TestCalculateLapTime:
    """Tests for simplified calculate_lap_time function."""

    def test_basic_calculation(self):
        """Basic calculation should work."""
        time = calculate_lap_time(
            base_lap_time=90.0,
            car_performance=80,
            driver_skill=80,
            fuel_mass=50,
            tyre_compound="medium",
            tyre_age=10,
            tyre_wear=0.3,
        )

        assert isinstance(time, float)
        assert time > 0

    def test_car_performance_effect(self):
        """Car performance should affect lap time."""
        time_fast = calculate_lap_time(90, 90, 80, 50, "medium", 10, 0.3)
        time_slow = calculate_lap_time(90, 60, 80, 50, "medium", 10, 0.3)

        assert time_fast < time_slow

    def test_driver_skill_effect(self):
        """Driver skill should affect lap time."""
        time_fast = calculate_lap_time(90, 80, 90, 50, "medium", 10, 0.3)
        time_slow = calculate_lap_time(90, 80, 60, 50, "medium", 10, 0.3)

        assert time_fast < time_slow

    def test_fuel_effect(self):
        """Fuel mass should affect lap time."""
        time_light = calculate_lap_time(90, 80, 80, 10, "medium", 10, 0.3)
        time_heavy = calculate_lap_time(90, 80, 80, 100, "medium", 10, 0.3)

        assert time_light < time_heavy

    def test_tyre_compound_effect(self):
        """Tyre compound should affect lap time."""
        time_soft = calculate_lap_time(90, 80, 80, 50, "soft", 5, 0.1)
        time_medium = calculate_lap_time(90, 80, 80, 50, "medium", 5, 0.1)
        time_hard = calculate_lap_time(90, 80, 80, 50, "hard", 5, 0.1)

        assert time_soft < time_medium < time_hard

    def test_tyre_age_effect(self):
        """Tyre age should affect lap time."""
        time_new = calculate_lap_time(90, 80, 80, 50, "medium", 1, 0.0)
        time_old = calculate_lap_time(90, 80, 80, 50, "medium", 25, 0.8)

        assert time_new < time_old

    def test_weather_effect(self):
        """Weather should affect lap time."""
        time_dry = calculate_lap_time(90, 80, 80, 50, "medium", 10, 0.3, weather_grip=1.0)
        time_wet = calculate_lap_time(90, 80, 80, 50, "medium", 10, 0.3, weather_grip=0.8)

        assert time_dry < time_wet

    def test_drs_effect(self):
        """DRS should reduce lap time."""
        time_no_drs = calculate_lap_time(90, 80, 80, 50, "medium", 10, 0.3, drs_active=False)
        time_drs = calculate_lap_time(90, 80, 80, 50, "medium", 10, 0.3, drs_active=True)

        assert time_drs < time_no_drs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
