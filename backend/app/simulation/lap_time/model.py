from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app.simulation.core.random import RandomProvider
from app.simulation.core.state import LapTimeComponents
from app.simulation.models.car import Car
from app.simulation.models.driver import Driver
from app.simulation.models.track import Track
from app.simulation.models.tyre import TyreCompound, TyreSpec
from app.simulation.models.weather import WeatherState


@dataclass
class LapTimeInputs:
    """All inputs needed for lap time calculation."""

    # Reference
    base_lap_time: float  # Track reference time

    # Car
    car: Car
    engine_power_kw: float

    # Driver
    driver: Driver
    driver_effective_skill: float

    # Tyre
    compound: TyreCompound
    tyre_spec: TyreSpec
    tyre_age_laps: int
    tyre_wear: float  # 0-1
    tyre_temp: float

    # Fuel
    fuel_mass: float  # kg
    fuel_per_lap: float  # kg/lap

    # Track
    track: Track
    track_evolution: float  # 0-1, how much track has improved
    track_grip: float  # 0-1, weather/track condition factor

    # Weather
    weather: WeatherState

    # Race situation
    is_qualifying: bool = False
    is_race_start: bool = False
    is_safety_car: bool = False
    is_vsc: bool = False
    drs_active: bool = False
    ers_mode: str = "medium"

    # Traffic
    in_traffic: bool = False
    traffic_loss: float = 0.0

    # Damage
    aero_damage: float = 0.0
    mechanical_damage: float = 0.0

    # Random
    rng: RandomProvider | None = None


class LapTimeModel(BaseModel):
    """Scientifically interpretable lap time model.
    
    lap_time = base_track_time * car_delta * driver_delta * fuel_delta * 
               tyre_delta * tyre_degradation * weather_delta * 
               traffic_delta * track_evolution_delta * stochastic_error
    
    All coefficients are configurable and documented.
    """

    # Model version
    model_version: str = "0.1.0"

    # Base coefficients (tunable)
    # Car performance sensitivity
    car_downforce_weight: float = 0.4
    car_aero_eff_weight: float = 0.2
    car_mechanical_weight: float = 0.2
    car_power_weight: float = 0.2

    # Driver skill sensitivity
    driver_skill_weight: float = 1.0
    driver_consistency_weight: float = 0.5

    # Fuel effect
    fuel_effect_per_10kg: float = 0.035  # seconds per 10kg
    fuel_effect_nonlinear: float = 1.0  # Exponent

    # Tyre
    tyre_base_grip_factor: float = 1.0
    tyre_degradation_sensitivity: float = 1.0
    tyre_temperature_sensitivity: float = 0.02  # sec per degree outside window

    # Weather
    weather_grip_sensitivity: float = 1.0
    rain_visibility_penalty: float = 1.5  # sec per lap in rain

    # Traffic
    traffic_base_loss: float = 0.3  # sec per lap in traffic
    traffic_sensitivity: float = 0.5  # multiplier for gap

    # Track evolution
    track_evo_per_lap: float = 0.02  # sec per lap
    track_evo_saturation: float = 1.5  # max improvement

    # DRS/ERS
    drs_effect: float = 0.3  # sec
    ers_overtake_effect: float = 0.2  # sec per lap

    # Damage
    aero_damage_sensitivity: float = 2.0  # sec at 100% damage
    mechanical_damage_sensitivity: float = 3.0

    # Stochastic
    base_variation: float = 0.05  # sec standard deviation
    variation_scaling: float = 1.0

    # Minimum lap time (prevents unrealistic times)
    min_lap_time_factor: float = 0.95  # vs base

    model_config = {"arbitrary_types_allowed": True}

    def calculate_lap_time(self, inputs: LapTimeInputs) -> LapTimeComponents:
        """Calculate lap time with full component breakdown."""
        rng = inputs.rng or RandomProvider()

        # 1. Base track time
        base_time = inputs.base_lap_time

        # 2. Car delta
        car_perf = self._calculate_car_performance(inputs.car, inputs.engine_power_kw)
        car_delta = self._performance_to_delta(car_perf)

        # 3. Driver delta
        driver_perf = self._calculate_driver_performance(inputs)
        driver_delta = self._performance_to_delta(driver_perf)

        # 4. Fuel delta
        fuel_delta = self._calculate_fuel_delta(inputs.fuel_mass)

        # 5. Tyre delta (base compound pace)
        tyre_delta = self._calculate_tyre_base_delta(inputs)

        # 6. Tyre degradation
        tyre_deg_delta = self._calculate_tyre_degradation_delta(inputs)

        # 7. Weather delta
        weather_delta = self._calculate_weather_delta(inputs.weather, inputs.track)

        # 8. Traffic delta
        traffic_delta = self._calculate_traffic_delta(inputs)

        # 9. Track evolution delta
        track_evo_delta = self._calculate_track_evolution_delta(inputs.track_evolution)

        # 10. DRS delta
        drs_delta = self._calculate_drs_delta(inputs)

        # 11. ERS delta
        ers_delta = self._calculate_ers_delta(inputs)

        # 12. Damage delta
        damage_delta = self._calculate_damage_delta(inputs)

        # 13. Stochastic delta
        stochastic_delta = self._calculate_stochastic_delta(rng, inputs)

        # Combine multiplicatively (or additively for small deltas)
        # Using additive for clarity: total = base * (1 + sum of deltas)
        total_delta = (
            car_delta + driver_delta + fuel_delta + tyre_delta +
            tyre_deg_delta + weather_delta + traffic_delta +
            track_evo_delta + drs_delta + ers_delta + damage_delta + stochastic_delta
        )

        total_time = base_time * (1.0 + total_delta)

        # Apply minimum
        min_time = base_time * self.min_lap_time_factor
        total_time = max(min_time, total_time)

        return LapTimeComponents(
            base_time=base_time,
            car_delta=car_delta,
            driver_delta=driver_delta,
            fuel_delta=fuel_delta,
            tyre_delta=tyre_delta,
            tyre_degradation_delta=tyre_deg_delta,
            weather_delta=weather_delta,
            traffic_delta=traffic_delta,
            track_evolution_delta=track_evo_delta,
            drs_delta=drs_delta,
            ers_delta=ers_delta,
            damage_delta=damage_delta,
            stochastic_delta=stochastic_delta,
            total=total_time,
        )

    def _calculate_car_performance(self, car: Car, engine_power: float) -> float:
        """Calculate car performance index (0-100)."""
        # Weighted combination of car attributes
        perf = (
            self.car_downforce_weight * car.overall_downforce +
            self.car_aero_eff_weight * car.aero_efficiency +
            self.car_mechanical_weight * car.mechanical_grip +
            self.car_power_weight * (engine_power / 10)  # ~750kW -> 75
        ) / (self.car_downforce_weight + self.car_aero_eff_weight +
             self.car_mechanical_weight + self.car_power_weight)

        # Setup quality bonus (placeholder)
        return perf

    def _calculate_driver_performance(self, inputs: LapTimeInputs) -> float:
        """Calculate driver performance index (0-100)."""
        base = inputs.driver_effective_skill

        # Consistency bonus (more consistent = better average)
        consistency_bonus = (inputs.driver.consistency - 50) * self.driver_consistency_weight / 100 * 5  # noqa: E501

        # Race start bonus
        if inputs.is_race_start:
            start_bonus = (inputs.driver.start_performance - 50) / 100 * 3
            base += start_bonus

        return base + consistency_bonus

    def _performance_to_delta(self, performance: float) -> float:
        """Convert 0-100 performance to time delta factor.
        
        100 performance = -3% (faster), 0 performance = +3% (slower)
        50 performance = 0%
        """
        # Linear mapping: -0.03 to +0.03
        return (performance - 50) / 50 * -0.03

    def _calculate_fuel_delta(self, fuel_mass: float) -> float:
        """Calculate fuel effect delta."""
        # Reference is ~50kg (mid-race)
        ref_fuel = 50.0
        delta_fuel = fuel_mass - ref_fuel
        # Seconds per 10kg, converted to fraction of lap time
        sec_per_10kg = self.fuel_effect_per_10kg
        # Assuming ~90s lap time
        return (delta_fuel / 10.0) * sec_per_10kg / 90.0

    def _calculate_tyre_base_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate base tyre compound delta."""
        # Tyre spec pace_factor: 1.0 = medium, <1.0 = faster, >1.0 = slower
        # Convert to delta fraction
        pace_factor = inputs.tyre_spec.base_pace_factor
        return (pace_factor - 1.0) * 0.5  # Roughly 0.5-1.5% range

    def _calculate_tyre_degradation_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate tyre degradation delta."""
        if inputs.tyre_age_laps <= 0:
            return 0.0

        spec = inputs.tyre_spec

        # Base degradation from spec
        deg = spec.degradation_rate * (inputs.tyre_age_laps ** spec.degradation_exponent)

        # Cliff effect
        if inputs.tyre_wear >= spec.cliff_threshold:
            cliff_progress = (inputs.tyre_wear - spec.cliff_threshold) / (1.0 - spec.cliff_threshold)  # noqa: E501
            deg *= 1.0 + cliff_progress * (spec.cliff_severity - 1.0)

        # Car tyre wear sensitivity
        car_wear = (inputs.car.tyre_wear_front + inputs.car.tyre_wear_rear) / 2
        car_factor = 1.2 - (car_wear / 100) * 0.4
        deg *= car_factor

        # Track surface roughness
        track_rough = (inputs.track.front_tyre_stress + inputs.track.rear_tyre_stress) / 200
        deg *= (0.8 + track_rough * 0.4)

        # Convert seconds to fraction
        return deg / inputs.base_lap_time * self.tyre_degradation_sensitivity

    def _calculate_weather_delta(self, weather: WeatherState, track: Track) -> float:
        """Calculate weather effect delta."""
        cond = weather.condition.value if hasattr(weather.condition, 'value') else weather.condition
        if cond == "dry":
            return 0.0

        # Grip multiplier from weather
        grip_mult = weather.get_grip_multiplier()
        # Convert to time delta (less grip = slower)
        delta = (1.0 / grip_mult - 1.0) * self.weather_grip_sensitivity

        # Visibility penalty
        if cond in ("light_rain", "heavy_rain"):
            delta += self.rain_visibility_penalty / track.reference_lap_time

        return delta

    def _calculate_traffic_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate traffic delta."""
        if not inputs.in_traffic:
            return 0.0

        # Base loss + sensitivity to gap
        base_loss = self.traffic_base_loss / inputs.base_lap_time
        gap_factor = 1.0 + inputs.traffic_loss * self.traffic_sensitivity

        return base_loss * gap_factor

    def _calculate_track_evolution_delta(self, evolution: float) -> float:
        """Calculate track evolution delta (negative = faster)."""
        # Evolution saturates
        effective_evo = min(evolution, self.track_evo_saturation)
        return -effective_evo * self.track_evo_per_lap / 90.0  # per 90s lap

    def _calculate_drs_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate DRS effect delta."""
        if not inputs.drs_active:
            return 0.0

        # DRS effect depends on track and car
        track_drs = inputs.track.get_drs_effectiveness()
        car_drs = inputs.car.drs_effectiveness / 100
        combined = track_drs * car_drs * self.drs_effect

        return -combined / inputs.base_lap_time

    def _calculate_ers_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate ERS effect delta."""
        if inputs.ers_mode == "overtake":
            return -self.ers_overtake_effect / inputs.base_lap_time
        elif inputs.ers_mode == "attack":
            return -self.ers_overtake_effect * 0.5 / inputs.base_lap_time
        elif inputs.ers_mode == "conserve":
            return self.ers_overtake_effect * 0.2 / inputs.base_lap_time
        return 0.0

    def _calculate_damage_delta(self, inputs: LapTimeInputs) -> float:
        """Calculate damage delta."""
        aero = inputs.aero_damage * self.aero_damage_sensitivity / inputs.base_lap_time
        mech = inputs.mechanical_damage * self.mechanical_damage_sensitivity / inputs.base_lap_time
        return aero + mech

    def _calculate_stochastic_delta(self, rng: RandomProvider, inputs: LapTimeInputs) -> float:
        """Calculate stochastic variation."""
        # Base variation scaled by driver consistency
        consistency_factor = inputs.driver.get_consistency_factor()
        std_dev = self.base_variation * consistency_factor * self.variation_scaling

        # Generate variation
        variation = rng.normal(0, std_dev)

        # Convert to fraction
        return variation / inputs.base_lap_time


# Convenience function for quick lap time calculation
def calculate_lap_time(
    base_lap_time: float,
    car_performance: float,  # 0-100
    driver_skill: float,  # 0-100
    fuel_mass: float,
    tyre_compound: str,
    tyre_age: int,
    tyre_wear: float,
    weather_grip: float = 1.0,
    traffic_loss: float = 0.0,
    track_evolution: float = 0.0,
    drs_active: bool = False,
    rng: RandomProvider | None = None,
) -> float:
    """Simplified lap time calculation for quick estimates."""
    rng = rng or RandomProvider()

    # Car delta
    car_delta = (car_performance - 50) / 50 * -0.03

    # Driver delta
    driver_delta = (driver_skill - 50) / 50 * -0.03

    # Fuel delta
    fuel_delta = ((fuel_mass - 50) / 10) * 0.035 / 90

    # Tyre compound delta
    compound_base = {"soft": -0.015, "medium": 0.0, "hard": 0.015, "intermediate": 0.05, "wet": 0.10}  # noqa: E501
    tyre_delta = compound_base.get(tyre_compound, 0.0)

    # Tyre degradation
    tyre_deg = 0.05 * (tyre_age ** 1.2) / 90 if tyre_age > 0 else 0
    tyre_deg *= (1 + tyre_wear)

    # Weather
    weather_delta = (1.0 / weather_grip - 1.0) if weather_grip < 1.0 else 0

    # Traffic
    traffic_delta = traffic_loss / 90

    # Track evolution
    track_evo_delta = -min(track_evolution, 1.5) * 0.02 / 90

    # DRS
    drs_delta = -0.3 / 90 if drs_active else 0

    # Stochastic
    stochastic = rng.normal(0, 0.05) / 90

    total_delta = sum([car_delta, driver_delta, fuel_delta, tyre_delta,
                      tyre_deg, weather_delta, traffic_delta, track_evo_delta,
                      drs_delta, stochastic])

    return base_lap_time * (1 + total_delta)
