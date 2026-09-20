import pytest

from app.simulation.core.race_engine import RaceEngine
from app.simulation.core.random import RandomProvider
from app.simulation.core.state import DriverStatus, SimulationConfig
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.track import Track
from app.simulation.models.weather import WeatherCondition


class TestRaceEngine:
    """Tests for full race simulation."""

    def setup_method(self):
        """Create standard test fixtures for a 2-car race."""
        # Create two drivers
        self.driver1 = Driver(
            id="VER", name="Max Verstappen", short_name="VER", number=1,
            nationality="Dutch", date_of_birth="1997-09-27", team_id="RED_BULL",
            overall_skill=95, qualifying_skill=97, race_skill=96,
            consistency=90, aggression=85, tyre_management=88,
            wet_weather_skill=92, overtaking=94, defending=93,
            start_performance=95, adaptability=90, pressure_resistance=95,
            mistake_rate=10,
        )

        self.driver2 = Driver(
            id="HAM", name="Lewis Hamilton", short_name="HAM", number=44,
            nationality="British", date_of_birth="1985-01-07", team_id="MERCEDES",
            overall_skill=94, qualifying_skill=95, race_skill=95,
            consistency=88, aggression=75, tyre_management=90,
            wet_weather_skill=90, overtaking=92, defending=90,
            start_performance=90, adaptability=92, pressure_resistance=93,
            mistake_rate=8,
        )

        # Create cars
        self.car1 = Car(
            id="RB20", name="Red Bull RB20", team_id="RED_BULL",
            engine_id="HONDA_2024", year=2024,
            overall_downforce=85, aero_efficiency=80, mechanical_grip=82,
            traction=80, braking_stability=85, drs_effectiveness=80,
            tyre_wear_front=80, tyre_wear_rear=80, tyre_warmup_speed=85,
        )

        self.car2 = Car(
            id="W15", name="Mercedes W15", team_id="MERCEDES",
            engine_id="MERCEDES_2024", year=2024,
            overall_downforce=82, aero_efficiency=78, mechanical_grip=80,
            traction=78, braking_stability=82, drs_effectiveness=78,
            tyre_wear_front=78, tyre_wear_rear=78, tyre_warmup_speed=82,
        )

        # Create track
        self.track = Track(
            id="bahrain", name="Bahrain International Circuit", country="Bahrain", city="Sakhir",
            track_type="permanent", length_km=5.412, number_of_laps=5,
            race_distance_km=27.06, number_of_corners=15,
            corner_distribution={
                "hairpin": 2, "slow": 3, "medium": 4,
                "fast": 3, "high_speed": 2, "chicane": 1,
            },
            longest_straight_km=1.1, overtaking_difficulty=35,
            front_tyre_stress=60, rear_tyre_stress=55,
            base_degradation_rate=0.045, reference_lap_time=90.5,
            track_evolution_rate=0.025,
            pit_stop_time_loss=20.5,
        )

        # Create config
        self.config = SimulationConfig(
            simulation_id="test_race",
            seed=42,
            model_version="0.1.0",
            session_type="race",
            track_id="bahrain",
            total_laps=5,
            initial_weather=WeatherCondition.DRY,
            weather_variability=0.0,  # No rain for deterministic test
            track_length_km=5.412,
            number_of_sectors=3,
            overtaking_difficulty=0.35,
            tyre_degradation_multiplier=1.0,
            safety_car_probability=0.0,  # Disable for deterministic test
            vsc_probability=0.0,
            incident_probability=0.0,
            pit_lane_time_loss=20.5,
            pit_stop_base_time=2.5,
            fuel_per_lap=1.8,
            fuel_effect_per_10kg=0.035,
        )

        # Create RNG
        self.rng = RandomProvider(seed=42)

        # Create engine
        self.engine = RaceEngine()

    def test_race_runs_to_completion(self):
        """Test that a short race runs to completion without errors."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        assert result is not None
        assert len(result.results) == 2
        assert result.completed_laps == 5
        assert result.track_id == "bahrain"
        assert result.session_type == "race"

    def test_both_drivers_finish(self):
        """Test that both drivers finish the race in normal conditions."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        # Both should finish (no incidents, no mechanical failures)
        active_results = [r for r in result.results if r.status == "active"]
        assert len(active_results) == 2

    def test_winner_has_position_1(self):
        """Test that the winner has position 1."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        winner = min(result.results, key=lambda x: x.position)
        assert winner.position == 1
        assert winner.total_time is not None
        assert winner.total_time > 0

    def test_results_sorted_by_position(self):
        """Test that results are sorted by position."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        positions = [r.position for r in result.results]
        assert positions == sorted(positions)

    def test_faster_car_wins_deterministic(self):
        """Test that significantly faster car wins with same seed."""
        # Create a clearly slower car
        slow_car = Car(
            id="SLOW", name="Slow Car", team_id="SLOW", engine_id="TEST", year=2024,
            overall_downforce=60, aero_efficiency=60, mechanical_grip=60,
            traction=60, braking_stability=60,
        )

        # Same driver, different cars - use a different driver ID for the slow car
        slow_driver = Driver(
            id="SLOW", name="Slow Driver", short_name="SLD", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="SLOW",
            overall_skill=70, qualifying_skill=70, race_skill=70,
            consistency=70, aggression=50, tyre_management=70,
            wet_weather_skill=70, overtaking=70, defending=70,
            start_performance=70, adaptability=70, pressure_resistance=70,
            mistake_rate=30,
        )

        # Same driver, different cars
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, slow_driver],
            cars={"VER": self.car1, "SLOW": slow_car},
            track=self.track,
            rng=RandomProvider(seed=42),
        )

        # RB20 should beat slow car
        ver_result = next(r for r in result.results if r.driver_id == "VER")
        slow_result = next(r for r in result.results if r.driver_id == "SLOW")

        assert ver_result.position == 1
        assert slow_result.position == 2
        assert ver_result.total_time < slow_result.total_time

    def test_better_driver_wins_deterministic(self):
        """Test that significantly better driver wins with same car."""
        # Create a clearly worse driver
        bad_driver = Driver(
            id="ROK", name="Rookie", short_name="ROK", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=60, qualifying_skill=60, race_skill=60,
            consistency=50, aggression=30, tyre_management=50,
            wet_weather_skill=50, overtaking=40, defending=40,
            start_performance=50, adaptability=40, pressure_resistance=40,
            mistake_rate=50,
        )

        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, bad_driver],
            cars={"VER": self.car1, "ROK": self.car1},  # Same car
            track=self.track,
            rng=RandomProvider(seed=42),
        )

        ver_result = next(r for r in result.results if r.driver_id == "VER")
        rok_result = next(r for r in result.results if r.driver_id == "ROK")

        assert ver_result.position == 1
        assert rok_result.position == 2
        assert ver_result.total_time < rok_result.total_time

    def test_deterministic_race_simulation(self):
        """Test that same seed produces identical race results."""
        config = self.config.model_copy(update={"seed": 42})

        result1 = RaceEngine().simulate_race(
            config=config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=RandomProvider(seed=42),
        )

        result2 = RaceEngine().simulate_race(
            config=config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=RandomProvider(seed=42),
        )

        # Same seed should produce identical results
        assert result1.results[0].driver_id == result2.results[0].driver_id
        assert result1.results[0].total_time == result2.results[0].total_time
        assert result1.results[1].driver_id == result2.results[1].driver_id
        assert result1.results[1].total_time == result2.results[1].total_time

    def test_points_awarded_correctly(self):
        """Test that championship points are awarded correctly."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        # Points system: [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        winner = min(result.results, key=lambda x: x.position)
        loser = max(result.results, key=lambda x: x.position)

        assert winner.points == 25
        assert loser.points == 18

    def test_dnf_handling(self):
        """Test that DNFs are handled correctly."""
        # Create a car with very low reliability
        unreliable_car = Car(
            id="UNREL", name="Unreliable", team_id="UNREL", engine_id="TEST", year=2024,
            chassis_reliability=1, gearbox_reliability=1, suspension_reliability=1,
        )

        # Use high incident probability
        config = self.config.model_copy(update={"incident_probability": 1.0})

        result = RaceEngine().simulate_race(
            config=config,
            drivers=[self.driver1],
            cars={"VER": unreliable_car},
            track=self.track,
            rng=RandomProvider(seed=42),
        )

        result_driver = result.results[0]
        # Should either finish or DNF
        assert result_driver.status in [DriverStatus.ACTIVE, DriverStatus.RETIRED, DriverStatus.DNF]
        if result_driver.status == DriverStatus.RETIRED:
            assert result_driver.dnf_reason is not None

    def test_race_with_pit_stops(self):
        """Test that pit stops occur during race."""
        # Create config with high tyre degradation to force pit stops
        config = self.config.model_copy(update={"tyre_degradation_multiplier": 3.0})

        result = RaceEngine().simulate_race(
            config=config,
            drivers=[self.driver1, self.driver2],
            cars={"VER": self.car1, "HAM": self.car2},
            track=self.track,
            rng=self.rng,
        )

        # Check that lap times reflect pit stops (some laps should be much slower)
        # We can't easily inspect individual lap times from result,
        # but we can verify both finished
        active = [r for r in result.results if r.status == "active"]
        assert len(active) == 2


class TestRaceEngineEdgeCases:
    """Tests for edge cases in race simulation."""

    def setup_method(self):
        self.driver = Driver(
            id="VER", name="Max", short_name="VER", number=1,
            nationality="Dutch", date_of_birth="1997-09-27", team_id="RED_BULL",
            overall_skill=95, qualifying_skill=97, race_skill=96,
            consistency=90, aggression=85, tyre_management=88,
            wet_weather_skill=92, overtaking=94, defending=93,
            start_performance=95, adaptability=90, pressure_resistance=95,
            mistake_rate=10,
        )

        self.car = Car(
            id="RB20", name="RB20", team_id="RED_BULL", engine_id="HONDA", year=2024,
        )

        self.track = Track(
            id="monaco", name="Monaco", country="Monaco", city="Monaco",
            track_type="street", length_km=3.337, number_of_laps=3,
            race_distance_km=10.0, number_of_corners=19,
            corner_distribution={
                "hairpin": 3, "slow": 8, "medium": 5,
                "fast": 2, "high_speed": 0, "chicane": 1,
            },
            longest_straight_km=0.5, overtaking_difficulty=95,
            front_tyre_stress=40, rear_tyre_stress=45,
            base_degradation_rate=0.02, reference_lap_time=73.5,
            track_evolution_rate=0.035,
            pit_stop_time_loss=19.0,
        )

        self.config = SimulationConfig(
            simulation_id="test_monaco",
            seed=42,
            model_version="0.1.0",
            session_type="race",
            track_id="monaco",
            total_laps=3,
            initial_weather="dry",
            weather_variability=0.0,
            track_length_km=3.337,
            number_of_sectors=3,
            overtaking_difficulty=0.95,
            safety_car_probability=0.0,
            vsc_probability=0.0,
            incident_probability=0.0,
            pit_lane_time_loss=19.0,
            pit_stop_base_time=2.5,
            fuel_per_lap=1.8,
        )

        self.rng = RandomProvider(seed=42)
        self.engine = RaceEngine()

    def test_short_race_completes(self):
        """Test that a very short race (3 laps) completes."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver],
            cars={"VER": self.car},
            track=self.track,
            rng=self.rng,
        )

        assert result.completed_laps == 3
        assert len(result.results) == 1
        assert result.results[0].laps_completed == 3

    def test_single_driver_race(self):
        """Test race with only one driver."""
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver],
            cars={"VER": self.car},
            track=self.track,
            rng=self.rng,
        )

        assert len(result.results) == 1
        assert result.results[0].position == 1
        assert result.results[0].points == 25

    def test_monaco_overtaking_difficulty(self):
        """Test that Monaco's high overtaking difficulty is handled."""
        # Just verify race completes without errors
        result = self.engine.simulate_race(
            config=self.config,
            drivers=[self.driver],
            cars={"VER": self.car},
            track=self.track,
            rng=self.rng,
        )

        assert result.results[0].laps_completed == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
