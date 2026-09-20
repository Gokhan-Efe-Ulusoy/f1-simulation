from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app.simulation.core.random import RandomProvider
from app.simulation.models.car import Car
from app.simulation.models.track import Track
from app.simulation.models.tyre import TyreCompound, TyreSpec, TyreState, get_standard_tyre_specs
from app.simulation.models.weather import WeatherState


@dataclass
class TyrePhysicsInputs:
    """Inputs for tyre physics calculation."""

    # Tyre
    compound: TyreCompound
    spec: TyreSpec
    state: TyreState

    # Car
    car: Car

    # Track
    track: Track

    # Conditions
    weather: WeatherState
    track_temp: float
    track_wetness: float

    # Driving
    fuel_mass: float
    is_pushing: bool = False
    is_cooling: bool = False
    in_traffic: bool = False

    # Lap
    lap_number: int = 0
    stint_lap: int = 0  # Lap within current stint

    # Random
    rng: RandomProvider | None = None


class TyreModel(BaseModel):
    """Tyre physics model for temperature, wear, and degradation."""

    # Temperature model
    ambient_heat_transfer: float = 0.02  # How fast tyres approach ambient
    track_heat_transfer: float = 0.15  # How fast tyres heat from track
    braking_heat: float = 0.5  # Heat from braking per heavy zone
    cornering_heat: float = 0.3  # Heat from cornering per corner
    sliding_heat: float = 2.0  # Heat from sliding/overheating
    cooling_in_pits: float = 5.0  # Cooling per second in pits

    # Wear model
    base_wear_per_lap: float = 0.03  # At reference conditions
    wear_fuel_sensitivity: float = 0.01  # Extra wear per 10kg fuel
    wear_aggression_sensitivity: float = 0.02  # Extra wear when pushing
    wear_traffic_sensitivity: float = 0.005  # Extra wear in dirty air
    wear_track_roughness_sensitivity: float = 0.02

    # Pressure
    pressure_rise_per_lap: float = 0.05  # PSI per lap
    pressure_rise_per_10deg: float = 0.3  # PSI per 10C temp rise
    optimal_pressure_window: float = 1.5  # PSI window

    # Flatspot
    lockup_flatspot_chance: float = 0.3  # Probability of flatspot on lockup
    flatspot_severity: tuple[float, float] = (0.1, 0.4)  # Min/max flatspot

    # Grip
    grip_temp_curve_width: float = 15.0  # Degrees for 90% grip

    model_config = {"arbitrary_types_allowed": True}

    def step(self, inputs: TyrePhysicsInputs) -> TyreState:
        """Advance tyre state by one lap."""
        rng = inputs.rng or RandomProvider()
        state = inputs.state.model_copy(deep=True)
        spec = inputs.spec

        # 1. Temperature evolution
        state = self._update_temperature(state, inputs)

        # 2. Wear evolution
        state = self._update_wear(state, inputs)

        # 3. Pressure evolution
        state = self._update_pressure(state, inputs)

        # 4. Age increment
        state.age_laps += 1
        state.stint_lap = inputs.stint_lap + 1

        return state

    def _update_temperature(self, state: TyreState, inputs: TyrePhysicsInputs) -> TyreState:
        """Update tyre temperatures."""
        spec = inputs.spec
        car = inputs.car
        track = inputs.track
        weather = inputs.weather

        # Target temperature based on track temp and workload
        base_target = inputs.track_temp + 15  # Tyres typically 15C above track

        # Adjust for compound
        if inputs.compound == TyreCompound.SOFT:
            base_target += 5
        elif inputs.compound == TyreCompound.HARD:
            base_target -= 5
        elif inputs.compound in (TyreCompound.INTERMEDIATE, TyreCompound.WET):
            base_target = inputs.track_temp + 5  # Run cooler

        # Adjust for pushing
        if inputs.is_pushing:
            base_target += 10
        elif inputs.is_cooling:
            base_target -= 10

        # Adjust for traffic (dirty air reduces cooling)
        if inputs.in_traffic:
            base_target += 5

        # Adjust for fuel (heavier car = more work)
        fuel_effect = (inputs.fuel_mass / 110) * 5
        base_target += fuel_effect

        # Each tyre heats differently
        # Fronts typically hotter due to braking
        targets = {
            "fl": base_target + 5,
            "fr": base_target + 5,
            "rl": base_target - 3,
            "rr": base_target - 3,
        }

        # Rear bias for traction-limited tracks
        if track.traction_energy > 70:
            targets["rl"] += 5
            targets["rr"] += 5

        # Update each tyre
        for corner in ["fl", "fr", "rl", "rr"]:
            current = getattr(state, f"temp_{corner}")
            target = targets[corner]

            # Heat transfer rate depends on speed/workload
            heating_rate = self.track_heat_transfer
            if inputs.is_pushing:
                heating_rate *= 1.5

            # Cooling from ambient/wet track
            cooling_rate = self.ambient_heat_transfer
            if weather.track_wetness > 0.3:
                cooling_rate *= 2.0  # Wet track cools faster

            # Newton's law of cooling/heating
            new_temp = current + (target - current) * heating_rate
            new_temp += inputs.rng.normal(0, 1.0)  # Small random variation

            setattr(state, f"temp_{corner}", new_temp)

        return state

    def _update_wear(self, state: TyreState, inputs: TyrePhysicsInputs) -> TyreState:
        """Update tyre wear."""
        spec = inputs.spec
        car = inputs.car
        track = inputs.track

        # Base wear rate from spec
        base_wear = spec.degradation_rate * (state.age_laps ** (spec.degradation_exponent - 1))

        # Car sensitivity
        car_wear_front = car.tyre_wear_front
        car_wear_rear = car.tyre_wear_rear
        car_wear_avg = (car_wear_front + car_wear_rear) / 2
        car_factor = 1.2 - (car_wear_avg / 100) * 0.4  # 0.8 to 1.2

        # Track roughness
        track_rough = (track.front_tyre_stress + track.rear_tyre_stress) / 200
        track_factor = 0.8 + track_rough * 0.4  # 0.8 to 1.2

        # Fuel effect
        fuel_factor = 1.0 + (inputs.fuel_mass / 110) * self.wear_fuel_sensitivity

        # Driving style
        driving_factor = 1.0
        if inputs.is_pushing:
            driving_factor += self.wear_aggression_sensitivity
        if inputs.is_cooling:
            driving_factor -= self.wear_aggression_sensitivity * 0.5

        # Traffic (sliding in dirty air)
        traffic_factor = 1.0
        if inputs.in_traffic:
            traffic_factor += self.wear_traffic_sensitivity

        # Weather
        weather_factor = 1.0
        if weather := inputs.weather:
            cond = weather.condition.value if hasattr(weather.condition, 'value') else weather.condition  # noqa: E501
            if cond in ("light_rain", "heavy_rain"):
                weather_factor = 0.7  # Less wear in wet (but more degradation)
            elif cond in ("damp", "wet"):
                weather_factor = 0.85

        # Calculate wear for this lap
        wear_rate = base_wear * car_factor * track_factor * fuel_factor * driving_factor * traffic_factor * weather_factor  # noqa: E501

        # Distribute between axles
        front_bias = 0.5 + inputs.car.front_rear_tyre_balance / 100  # -0.2 to 0.2 -> 0.3 to 0.7
        front_bias = max(0.3, min(0.7, front_bias))

        total_wear = wear_rate / spec.max_life_laps  # Normalize to 0-1 over max life

        state.wear = min(1.0, state.wear + total_wear)

        return state

    def _update_pressure(self, state: TyreState, inputs: TyrePhysicsInputs) -> TyreState:
        """Update tyre pressures."""
        # Pressure rises with temperature
        avg_temp = state.avg_temp
        temp_rise = max(0, avg_temp - 20)  # Reference 20C ambient
        pressure_rise = temp_rise / 10 * self.pressure_rise_per_10deg

        # Also rises per lap
        pressure_rise += state.age_laps * self.pressure_rise_per_lap

        # Starting pressure
        base_pressure = inputs.spec.optimal_pressure_psi

        for corner in ["fl", "fr", "rl", "rr"]:
            current = getattr(state, f"pressure_{corner}")
            # Small random variation
            new_pressure = base_pressure + pressure_rise + inputs.rng.normal(0, 0.1)
            setattr(state, f"pressure_{corner}", new_pressure)

        return state

    def calculate_grip(self, state: TyreState, spec: TyreSpec, track_temp: float) -> float:
        """Calculate current grip level (0-1)."""
        # Base grip from spec
        base_grip = spec.peak_grip

        # Wear effect
        wear_grip_loss = state.wear * spec.grip_drop_off
        base_grip *= (1.0 - wear_grip_loss)

        # Temperature effect
        temp_grip = self._temperature_grip_factor(state.avg_temp, spec)
        base_grip *= temp_grip

        # Pressure effect
        pressure_grip = self._pressure_grip_factor(state.avg_pressure, spec)
        base_grip *= pressure_grip

        # Flatspot
        if state.flatspot_severity > 0:
            base_grip *= (1.0 - state.flatspot_severity * 0.3)

        return max(0.1, base_grip)

    def _temperature_grip_factor(self, temp: float, spec: TyreSpec) -> float:
        """Grip factor from temperature (0-1, 1 = optimal)."""
        if spec.optimal_temp_min <= temp <= spec.optimal_temp_max:
            return 1.0
        elif temp < spec.optimal_temp_min:
            # Cold tyres
            diff = spec.optimal_temp_min - temp
            return max(0.5, 1.0 - diff / self.grip_temp_curve_width)
        else:
            # Overheating
            diff = temp - spec.optimal_temp_max
            return max(0.4, 1.0 - diff / self.grip_temp_curve_width * 1.5)

    def _pressure_grip_factor(self, pressure: float, spec: TyreSpec) -> float:
        """Grip factor from pressure (0-1, 1 = optimal)."""
        if abs(pressure - spec.optimal_pressure_psi) <= self.optimal_pressure_window / 2:
            return 1.0
        else:
            diff = abs(pressure - spec.optimal_pressure_psi) - self.optimal_pressure_window / 2
            return max(0.9, 1.0 - diff * 0.05)

    def simulate_lockup(self, state: TyreState, rng: RandomProvider) -> TyreState:
        """Simulate a lockup event."""
        if rng.random() < self.lockup_flatspot_chance:
            severity = rng.uniform(self.flatspot_severity[0], self.flatspot_severity[1])
            # Front tyres more likely to flatspot
            if rng.random() < 0.7:
                state.flatspot_severity = max(state.flatspot_severity, severity)
            # Wear spike
            state.wear = min(1.0, state.wear + 0.02)
        return state

    def simulate_puncture(self, state: TyreState, rng: RandomProvider, corner: str) -> TyreState:
        """Simulate a puncture."""
        state.tyre_damage = corner
        state.wear = 1.0  # Immediate failure
        state.puncture_risk = 0.0
        return state

    def estimate_stint_length(
        self,
        compound: TyreCompound,
        car: Car,
        track: Track,
        fuel_start: float,
        weather: str = "dry",
        pushing_fraction: float = 0.0,
    ) -> int:
        """Estimate how many laps a tyre can last."""
        specs = get_standard_tyre_specs()
        spec = specs[compound]

        # Base life
        life = spec.max_life_laps

        # Car sensitivity
        car_wear = (car.tyre_wear_front + car.tyre_wear_rear) / 2
        car_factor = 1.2 - (car_wear / 100) * 0.4
        life *= car_factor

        # Track
        track_rough = (track.front_tyre_stress + track.rear_tyre_stress) / 200
        track_factor = 0.8 + track_rough * 0.4
        life *= track_factor

        # Fuel (average over stint)
        fuel_factor = 1.0 + (fuel_start / 2 / 110) * self.wear_fuel_sensitivity
        life /= fuel_factor

        # Driving style
        driving_factor = 1.0 + pushing_fraction * self.wear_aggression_sensitivity
        life /= driving_factor

        # Weather
        if weather in ("light_rain", "heavy_rain"):
            life *= 1.5  # Less wear but more degradation
        elif weather in ("damp", "wet"):
            life *= 1.2

        return max(5, min(spec.max_life_laps, int(life)))


# Default tyre model
DEFAULT_TYRE_MODEL = TyreModel()
