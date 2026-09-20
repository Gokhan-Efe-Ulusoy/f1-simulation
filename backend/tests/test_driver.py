import pytest

from app.simulation.models.driver import Driver, DriverStats


class TestDriver:
    """Tests for Driver model."""

    def test_driver_creation_valid(self):
        """Valid driver should be created successfully."""
        driver = Driver(
            id="VER",
            name="Max Verstappen",
            short_name="VER",
            number=1,
            nationality="Dutch",
            date_of_birth="1997-09-27",
            team_id="RED_BULL",
            overall_skill=95,
            qualifying_skill=97,
            race_skill=96,
            consistency=90,
            aggression=85,
            tyre_management=88,
            wet_weather_skill=92,
            overtaking=94,
            defending=93,
            start_performance=95,
            adaptability=90,
            pressure_resistance=95,
            mistake_rate=10,
        )
        assert driver.id == "VER"
        assert driver.overall_skill == 95

    def test_driver_skill_validation(self):
        """Skills should be validated to 0-100 range."""
        with pytest.raises(ValueError):
            Driver(
                id="TEST", name="Test", short_name="TST", number=99,
                nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
                overall_skill=150,  # Invalid
            )

        with pytest.raises(ValueError):
            Driver(
                id="TEST", name="Test", short_name="TST", number=99,
                nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
                overall_skill=-10,  # Invalid
            )

    def test_short_name_uppercased(self):
        """Short name should be uppercased and truncated to 3 chars."""
        driver = Driver(
            id="test", name="Test", short_name="ver", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
        )
        assert driver.short_name == "VER"

        driver2 = Driver(
            id="test2", name="Test2", short_name="verstappen", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
        )
        assert driver2.short_name == "VER"

    def test_driver_number_validation(self):
        """Driver number should be 0-99."""
        with pytest.raises(ValueError):
            Driver(
                id="TEST", name="Test", short_name="TST", number=100,
                nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            )

        with pytest.raises(ValueError):
            Driver(
                id="TEST", name="Test", short_name="TST", number=-1,
                nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            )

    def test_get_effective_skill_qualifying(self):
        """Effective skill should use qualifying skill for qualifying."""
        driver = Driver(
            id="VER", name="Max Verstappen", short_name="VER", number=1,
            nationality="Dutch", date_of_birth="1997-09-27", team_id="RED_BULL",
            qualifying_skill=97,
            race_skill=96,
            overall_skill=95,
        )

        qualifying_skill = driver.get_effective_skill("monaco", "dry", "qualifying")
        race_skill = driver.get_effective_skill("monaco", "dry", "race")

        # Qualifying should be higher for this driver
        assert qualifying_skill > race_skill
        # Should be close to qualifying_skill (97) with small adjustments
        assert 90 < qualifying_skill < 100

    def test_get_effective_skill_race(self):
        """Effective skill should use race skill for race."""
        driver = Driver(
            id="HAM", name="Lewis Hamilton", short_name="HAM", number=44,
            nationality="British", date_of_birth="1985-01-07", team_id="MERCEDES",
            qualifying_skill=95,
            race_skill=97,  # Better in race
            overall_skill=96,
        )

        race_skill = driver.get_effective_skill("silverstone", "dry", "race")
        qualifying_skill = driver.get_effective_skill("silverstone", "dry", "qualifying")

        assert race_skill > qualifying_skill

    def test_track_preference_bonus(self):
        """Preferred tracks should give bonus."""
        driver = Driver(
            id="TEST", name="Test", short_name="TST", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80,
            qualifying_skill=80,
            race_skill=80,
            preferred_tracks=["monaco", "spa"],
            disliked_tracks=["monza"],
        )

        monaco_skill = driver.get_effective_skill("monaco", "dry", "race")
        monza_skill = driver.get_effective_skill("monza", "dry", "race")
        neutral_skill = driver.get_effective_skill("bahrain", "dry", "race")

        assert monaco_skill > neutral_skill
        assert monza_skill < neutral_skill

    def test_wet_weather_bonus(self):
        """Wet weather skill should affect wet conditions."""
        driver_wet = Driver(
            id="WET", name="Wet Master", short_name="WET", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80,
            qualifying_skill=80,
            race_skill=80,
            wet_weather_skill=95,
        )

        driver_dry = Driver(
            id="DRY", name="Dry Specialist", short_name="DRY", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80,
            qualifying_skill=80,
            race_skill=80,
            wet_weather_skill=60,
        )

        wet_skill_wet = driver_wet.get_effective_skill("spa", "wet", "race")
        wet_skill_dry = driver_wet.get_effective_skill("spa", "dry", "race")
        dry_skill_wet = driver_dry.get_effective_skill("spa", "wet", "race")
        dry_skill_dry = driver_dry.get_effective_skill("spa", "dry", "race")

        # Wet master should be better in wet
        assert wet_skill_wet > dry_skill_wet
        # In dry they should be similar (same base skills)
        assert abs(wet_skill_dry - dry_skill_dry) < 5

    def test_pressure_effect(self):
        """Pressure should affect drivers based on pressure_resistance."""
        driver_clutch = Driver(
            id="CLUTCH", name="Clutch", short_name="CLU", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80, race_skill=80, pressure_resistance=95, mistake_rate=10,
        )

        driver_chokes = Driver(
            id="CHOKE", name="Choke", short_name="CHO", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overall_skill=80, race_skill=80, pressure_resistance=40, mistake_rate=40,
        )

        clutch_normal = driver_clutch.get_effective_skill("spa", "dry", "race", pressure=0)
        clutch_pressure = driver_clutch.get_effective_skill("spa", "dry", "race", pressure=1.0)

        choke_normal = driver_chokes.get_effective_skill("spa", "dry", "race", pressure=0)
        choke_pressure = driver_chokes.get_effective_skill("spa", "dry", "race", pressure=1.0)

        # Clutch driver should lose less under pressure
        clutch_loss = clutch_normal - clutch_pressure
        choke_loss = choke_normal - choke_pressure

        assert clutch_loss < choke_loss

    def test_get_overtaking_and_defending_skill(self):
        """Overtaking and defending skills should be pressure-adjusted."""
        driver = Driver(
            id="TEST", name="Test", short_name="TST", number=99,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            overtaking=90, defending=80, pressure_resistance=90,
        )

        overtake_normal = driver.get_overtaking_skill(pressure=0)
        overtake_pressure = driver.get_overtaking_skill(pressure=1.0)

        defend_normal = driver.get_defending_skill(pressure=0)
        defend_pressure = driver.get_defending_skill(pressure=1.0)

        # Both should decrease slightly under pressure
        assert overtake_pressure <= overtake_normal
        assert defend_pressure <= defend_normal

    def test_tyre_management_factor(self):
        """Tyre management factor should scale with skill."""
        driver_good = Driver(
            id="GOOD", name="Good", short_name="GOD", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            tyre_management=90,
        )

        driver_bad = Driver(
            id="BAD", name="Bad", short_name="BAD", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            tyre_management=50,
        )

        assert driver_good.get_tyre_management_factor() > driver_bad.get_tyre_management_factor()
        assert 0.8 <= driver_good.get_tyre_management_factor() <= 1.2

    def test_consistency_factor(self):
        """Consistency factor should scale with skill."""
        driver_consistent = Driver(
            id="CON", name="Consistent", short_name="CON", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            consistency=90,
        )

        driver_inconsistent = Driver(
            id="INC", name="Inconsistent", short_name="INC", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            consistency=50,
        )

        assert driver_consistent.get_consistency_factor() > driver_inconsistent.get_consistency_factor()
        assert 0.5 <= driver_consistent.get_consistency_factor() <= 1.0

    def test_mistake_probability(self):
        """Mistake probability should increase with pressure and mistake_rate."""
        driver_low_mistakes = Driver(
            id="LOW", name="Low", short_name="LOW", number=1,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            mistake_rate=10, pressure_resistance=90,
        )

        driver_high_mistakes = Driver(
            id="HIGH", name="High", short_name="HIGH", number=2,
            nationality="Test", date_of_birth="2000-01-01", team_id="TEST",
            mistake_rate=50, pressure_resistance=50,
        )

        base_rate = 0.01

        low_normal = driver_low_mistakes.get_mistake_probability(base_rate, pressure=0)
        low_pressure = driver_low_mistakes.get_mistake_probability(base_rate, pressure=1.0)

        high_normal = driver_high_mistakes.get_mistake_probability(base_rate, pressure=0)
        high_pressure = driver_high_mistakes.get_mistake_probability(base_rate, pressure=1.0)

        assert low_normal < high_normal
        assert low_pressure > low_normal
        assert high_pressure > high_normal


class TestDriverStats:
    """Tests for DriverStats."""

    def test_driver_stats_creation(self):
        stats = DriverStats(
            driver_id="VER",
            seasons=8,
            races=160,
            wins=54,
            podiums=98,
            poles=32,
            fastest_laps=40,
            championships=3,
            points=2500.5,
        )
        assert stats.driver_id == "VER"
        assert stats.win_rate == 0  # Not auto-calculated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
