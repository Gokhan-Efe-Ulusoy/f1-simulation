import pytest

from app.simulation.models.track import CornerType, Track, TrackType, get_2024_calendar


class TestTrack:
    """Tests for Track model."""

    def test_track_creation(self):
        track = Track(
            id="test",
            name="Test Circuit",
            country="Testland",
            city="Test City",
            track_type=TrackType.PERMANENT,
            length_km=5.0,
            number_of_laps=60,
            race_distance_km=300.0,
            number_of_corners=15,
        )
        assert track.id == "test"
        assert track.length_km == 5.0

    def test_corner_distribution(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            corner_distribution={
                CornerType.HAIRPIN: 2,
                CornerType.SLOW: 3,
                CornerType.MEDIUM: 5,
                CornerType.FAST: 3,
                CornerType.HIGH_SPEED: 1,
                CornerType.CHICANE: 1,
            },
        )

        total = track.get_corner_count()
        assert total == 15

        hairpin_ratio = track.get_corner_type_ratio(CornerType.HAIRPIN)
        assert hairpin_ratio == 2/15

    def test_overtaking_difficulty_normalized(self):
        track_easy = Track(
            id="easy", name="Easy", country="Test", city="Test",
            overtaking_difficulty=30,
        )

        track_hard = Track(
            id="hard", name="Hard", country="Test", city="Test",
            overtaking_difficulty=95,
        )

        assert track_easy.get_overtaking_difficulty_normalized() == 0.3
        assert track_hard.get_overtaking_difficulty_normalized() == 0.95

    def test_tyre_degradation_per_lap(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            front_tyre_stress=80,
            rear_tyre_stress=70,
            base_degradation_rate=0.05,
        )

        # Soft should degrade faster than medium
        soft_deg = track.get_tyre_degradation_per_lap("soft")
        medium_deg = track.get_tyre_degradation_per_lap("medium")
        hard_deg = track.get_tyre_degradation_per_lap("hard")

        assert soft_deg > medium_deg > hard_deg

    def test_fuel_sensitivity(self):
        track_high_accel = Track(
            id="high_accel", name="High Accel", country="Test", city="Test",
            corner_distribution={
                CornerType.HAIRPIN: 3,
                CornerType.SLOW: 4,
                CornerType.MEDIUM: 3,
                CornerType.FAST: 1,
                CornerType.HIGH_SPEED: 0,
                CornerType.CHICANE: 2,
            },
        )

        track_low_accel = Track(
            id="low_accel", name="Low Accel", country="Test", city="Test",
            corner_distribution={
                CornerType.HAIRPIN: 0,
                CornerType.SLOW: 1,
                CornerType.MEDIUM: 4,
                CornerType.FAST: 4,
                CornerType.HIGH_SPEED: 3,
                CornerType.CHICANE: 0,
            },
        )

        high_sens = track_high_accel.get_fuel_sensitivity()
        low_sens = track_low_accel.get_fuel_sensitivity()

        assert high_sens > low_sens

    def test_drs_effectiveness(self):
        track_long_drs = Track(
            id="long_drs", name="Long DRS", country="Test", city="Test",
            drs_zones=3,
            drs_zone_lengths_km=[0.8, 0.6, 0.5],
        )

        track_short_drs = Track(
            id="short_drs", name="Short DRS", country="Test", city="Test",
            drs_zones=1,
            drs_zone_lengths_km=[0.3],
        )

        assert track_long_drs.get_drs_effectiveness() > track_short_drs.get_drs_effectiveness()

    def test_track_evolution_per_lap(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            track_evolution_rate=0.03,
        )

        # More cars = faster evolution
        evo_10 = track.get_track_evolution_per_lap(10)
        evo_20 = track.get_track_evolution_per_lap(20)

        assert evo_20 > evo_10

    def test_base_lap_time_estimation(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            reference_lap_time=90.0,
        )

        # Better car/driver = faster lap time
        time_slow = track.get_base_lap_time(car_performance=60, driver_skill=60)
        time_fast = track.get_base_lap_time(car_performance=90, driver_skill=90)

        assert time_fast < time_slow
        # Roughly 0.15s per car point + 0.10s per driver point
        # 30 points each = ~7.5s difference
        assert time_slow - time_fast > 5.0

    def test_sector_times(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            length_km=6.0,
            number_of_sectors=3,
            sector_lengths_km=[2.0, 2.0, 2.0],
        )

        sectors = track.get_sector_times(90.0)
        assert len(sectors) == 3
        assert abs(sum(sectors) - 90.0) < 0.01
        assert all(abs(s - 30.0) < 0.01 for s in sectors)

        # Unequal sectors
        track2 = Track(
            id="test2", name="Test2", country="Test", city="Test",
            length_km=6.0,
            number_of_sectors=3,
            sector_lengths_km=[1.0, 3.0, 2.0],
        )

        sectors2 = track2.get_sector_times(90.0)
        assert abs(sectors2[0] - 15.0) < 0.01
        assert abs(sectors2[1] - 45.0) < 0.01
        assert abs(sectors2[2] - 30.0) < 0.01

    def test_track_type_category(self):
        track_high = Track(
            id="high", name="High Speed", country="Test", city="Test",
            corner_distribution={
                CornerType.HIGH_SPEED: 6,
                CornerType.FAST: 4,
                CornerType.MEDIUM: 2,
            },
        )

        track_low = Track(
            id="low", name="Low Speed", country="Test", city="Test",
            corner_distribution={
                CornerType.HAIRPIN: 4,
                CornerType.SLOW: 5,
                CornerType.MEDIUM: 2,
            },
        )

        track_street = Track(
            id="street", name="Street", country="Test", city="Test",
            track_type=TrackType.STREET,
        )

        assert track_high.get_track_type_category() == "high_downforce"
        assert track_low.get_track_type_category() == "low_downforce"
        assert track_street.get_track_type_category() == "street"

    def test_pit_lane_time_total(self):
        track = Track(
            id="test", name="Test", country="Test", city="Test",
            pit_lane_length_km=0.4,
            pit_lane_speed_limit_kmh=80,
            pit_stop_time_loss=22.0,
        )

        total = track.get_pit_lane_time_total()
        # Should be around 22s (pit lane time + stationary)
        assert 20 < total < 25

    def test_2024_calendar(self):
        calendar = get_2024_calendar()

        assert len(calendar) >= 6  # At least the ones we defined
        track_ids = [t.id for t in calendar]

        assert "bahrain" in track_ids
        assert "saudi_arabia" in track_ids
        assert "australia" in track_ids
        assert "monaco" in track_ids
        assert "spain" in track_ids
        assert "monza" in track_ids

        # Monaco should have highest overtaking difficulty
        monaco = next(t for t in calendar if t.id == "monaco")
        assert monaco.overtaking_difficulty == 95

        # Monza should have lowest
        monza = next(t for t in calendar if t.id == "monza")
        assert monza.overtaking_difficulty == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
