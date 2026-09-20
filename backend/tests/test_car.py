import pytest

from app.simulation.models.car import Car, Engine, EngineMode


class TestEngine:
    """Tests for Engine model."""

    def test_engine_creation(self):
        engine = Engine(
            id="HONDA_2024",
            name="Honda RA624H",
            manufacturer="Honda",
            supplier_id="HONDA",
            peak_power_kw=780,
            energy_recovery_efficiency=85,
            fuel_efficiency=80,
            reliability=90,
        )
        assert engine.id == "HONDA_2024"
        assert engine.peak_power_kw == 780

    def test_engine_power_output_by_mode(self):
        engine = Engine(
            id="TEST", name="Test", manufacturer="Test", supplier_id="TEST",
            peak_power_kw=750,
        )

        power_conserve = engine.get_power_output(EngineMode.CONSERVE)
        power_standard = engine.get_power_output(EngineMode.STANDARD)
        power_attack = engine.get_power_output(EngineMode.ATTACK)
        power_overtake = engine.get_power_output(EngineMode.OVERTAKE)
        power_quali = engine.get_power_output(EngineMode.QUALIFYING)

        assert power_conserve < power_standard < power_attack < power_overtake < power_quali

    def test_engine_fuel_burn_by_mode(self):
        engine = Engine(
            id="TEST", name="Test", manufacturer="Test", supplier_id="TEST",
            fuel_burn_rate_base=1.8,
        )

        fuel_conserve = engine.get_fuel_burn_rate(EngineMode.CONSERVE)
        fuel_standard = engine.get_fuel_burn_rate(EngineMode.STANDARD)
        fuel_attack = engine.get_fuel_burn_rate(EngineMode.ATTACK)

        assert fuel_conserve < fuel_standard < fuel_attack

    def test_engine_ers_deployment_by_mode(self):
        engine = Engine(
            id="TEST", name="Test", manufacturer="Test", supplier_id="TEST",
            ers_deployment_per_lap=4.0,
        )

        ers_conserve = engine.get_ers_deployment(EngineMode.CONSERVE)
        ers_standard = engine.get_ers_deployment(EngineMode.STANDARD)
        ers_overtake = engine.get_ers_deployment(EngineMode.OVERTAKE)

        assert ers_conserve < ers_standard < ers_overtake

    def test_engine_failure_probability_increases_with_distance(self):
        engine = Engine(
            id="TEST", name="Test", manufacturer="Test", supplier_id="TEST",
            reliability=85, max_race_distance_km=3000,
        )

        prob_start = engine.get_failure_probability(0, EngineMode.STANDARD)
        prob_mid = engine.get_failure_probability(1500, EngineMode.STANDARD)
        prob_end = engine.get_failure_probability(3000, EngineMode.STANDARD)

        assert prob_start <= prob_mid <= prob_end

    def test_engine_wear_reduces_power(self):
        engine = Engine(
            id="TEST", name="Test", manufacturer="Test", supplier_id="TEST",
            peak_power_kw=750, performance_loss_per_wear=1.0,
        )

        power_new = engine.get_power_output(EngineMode.STANDARD, wear=0.0)
        power_worn = engine.get_power_output(EngineMode.STANDARD, wear=0.5)

        assert power_worn < power_new


class TestCar:
    """Tests for Car model."""

    def test_car_creation(self):
        car = Car(
            id="RB20",
            name="Red Bull RB20",
            team_id="RED_BULL",
            engine_id="HONDA_2024",
            year=2024,
            overall_downforce=85,
            aero_efficiency=80,
            mechanical_grip=82,
            traction=80,
            braking_stability=85,
        )
        assert car.id == "RB20"
        assert car.team_id == "RED_BULL"

    def test_cornering_performance_by_type(self):
        car = Car(
            id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=80,
            front_downforce=80,
            rear_downforce=80,
            aero_efficiency=75,
            mechanical_grip=75,
            traction=70,
            front_suspension=75,
            rear_suspension=75,
            braking_stability=80,
        )

        slow = car.get_cornering_performance("slow")
        medium = car.get_cornering_performance("medium")
        fast = car.get_cornering_performance("fast")
        hairpin = car.get_cornering_performance("hairpin")
        chicane = car.get_cornering_performance("chicane")

        # All should be reasonable values
        assert 0 < slow < 100
        assert 0 < medium < 100
        assert 0 < fast < 100
        assert 0 < hairpin < 100
        assert 0 < chicane < 100

    def test_straight_line_performance_drs(self):
        car = Car(
            id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=70,
            drs_effectiveness=80,
        )

        # DRS should reduce drag coefficient
        drag_no_drs = car.get_drag_coefficient(drs_open=False)
        drag_drs = car.get_drag_coefficient(drs_open=True)

        assert drag_drs < drag_no_drs

    def test_tyre_degradation_multiplier(self):
        car_kind = Car(
            id="KIND", name="Kind", team_id="TEST", engine_id="TEST", year=2024,
            tyre_wear_front=90, tyre_wear_rear=90,
        )

        car_harsh = Car(
            id="HARSH", name="Harsh", team_id="TEST", engine_id="TEST", year=2024,
            tyre_wear_front=40, tyre_wear_rear=40,
        )

        kind_mult = car_kind.get_tyre_degradation_multiplier("front")
        harsh_mult = car_harsh.get_tyre_degradation_multiplier("front")

        assert kind_mult < harsh_mult  # Kind to tyres = less degradation
        assert 0.8 <= kind_mult <= 1.2
        assert 0.8 <= harsh_mult <= 1.2

    def test_tyre_warmup_factor(self):
        car_fast = Car(
            id="FAST", name="Fast", team_id="TEST", engine_id="TEST", year=2024,
            tyre_warmup_speed=90,
        )

        car_slow = Car(
            id="SLOW", name="Slow", team_id="TEST", engine_id="TEST", year=2024,
            tyre_warmup_speed=40,
        )

        fast_warmup = car_fast.get_tyre_warmup_factor()
        slow_warmup = car_slow.get_tyre_warmup_factor()

        assert fast_warmup < slow_warmup  # Faster warmup = fewer laps

    def test_fuel_efficiency_factor(self):
        car_efficient = Car(
            id="EFF", name="Efficient", team_id="TEST", engine_id="TEST", year=2024,
            aero_efficiency=90,
        )

        car_inefficient = Car(
            id="INEFF", name="Inefficient", team_id="TEST", engine_id="TEST", year=2024,
            aero_efficiency=50,
        )

        # More aero efficient = better fuel efficiency (lower factor)
        assert car_efficient.get_fuel_efficiency_factor() < car_inefficient.get_fuel_efficiency_factor()

    def test_drag_coefficient_drs(self):
        car = Car(
            id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=70,
            drs_effectiveness=80,
        )

        drag_no_drs = car.get_drag_coefficient(drs_open=False)
        drag_drs = car.get_drag_coefficient(drs_open=True)

        assert drag_drs < drag_no_drs

    def test_performance_index_by_track_type(self):
        car_high_df = Car(
            id="HIGH_DF", name="High DF", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=90, aero_efficiency=70, mechanical_grip=70,
        )

        car_low_df = Car(
            id="LOW_DF", name="Low DF", team_id="TEST", engine_id="TEST", year=2024,
            overall_downforce=60, aero_efficiency=90, mechanical_grip=70,
        )

        high_df_high = car_high_df.calculate_performance_index("high_downforce")
        high_df_low = car_high_df.calculate_performance_index("low_downforce")

        low_df_high = car_low_df.calculate_performance_index("high_downforce")
        low_df_low = car_low_df.calculate_performance_index("low_downforce")

        # High downforce car should be better on high downforce tracks
        assert high_df_high > high_df_low
        # Low downforce car should be better on low downforce tracks
        assert low_df_low > low_df_high

    def test_setup_sensitivity(self):
        car = Car(
            id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
        )

        # Front wing should have highest sensitivity
        fw_sens = car.get_setup_sensitivity("front_wing")
        rr_sens = car.get_setup_sensitivity("rear_anti_roll")

        assert fw_sens > rr_sens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
