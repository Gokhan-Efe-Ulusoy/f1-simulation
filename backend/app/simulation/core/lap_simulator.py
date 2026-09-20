from __future__ import annotations

from pydantic import BaseModel

from app.simulation.core.random import RandomProvider
from app.simulation.core.state import DriverState, LapTimeComponents, RaceState
from app.simulation.lap_time.model import LapTimeInputs, LapTimeModel
from app.simulation.models.car import Car, EngineMode
from app.simulation.models.driver import Driver
from app.simulation.models.incident import Incident, IncidentModel, IncidentSeverity, IncidentType
from app.simulation.models.track import Track
from app.simulation.models.tyre import get_standard_tyre_specs
from app.simulation.models.weather import WeatherState
from app.simulation.tyre.model import DEFAULT_TYRE_MODEL, TyreModel, TyrePhysicsInputs


class LapResult(BaseModel):
    """Detailed result of a single simulated lap."""

    driver_id: str
    lap_number: int
    lap_time: float
    sector_times: list[float]

    # Tyre state after lap
    tyre_wear: float
    tyre_temp: float
    tyre_age: int

    # Fuel state after lap
    fuel_remaining: float

    # Overtaking / Incidents
    incident: Incident | None = None
    time_loss: float = 0.0

    # Component breakdown of the time
    components: LapTimeComponents

    model_config = {"arbitrary_types_allowed": True}


class LapSimulator(BaseModel):
    """Simulator for a single lap of a driver."""

    lap_time_model: LapTimeModel = LapTimeModel()
    tyre_physics_model: TyreModel = DEFAULT_TYRE_MODEL
    incident_model: IncidentModel = IncidentModel()

    model_config = {"arbitrary_types_allowed": True}

    def simulate_lap(
        self,
        lap_number: int,
        driver: Driver,
        car: Car,
        driver_state: DriverState,
        race_state: RaceState,
        track: Track,
        weather: WeatherState,
        rng: RandomProvider,
        is_qualifying: bool = False,
        is_race_start: bool = False,
        drs_active: bool = False,
    ) -> LapResult:
        """Simulate a single lap for a single driver."""
        # 1. Weather and track grip factors
        track_grip = weather.get_grip_multiplier()

        # 2. Tyre specs
        specs = get_standard_tyre_specs()
        tyre_spec = specs[driver_state.tyre_compound]

        # 3. Handle incident generation before/during lap
        # Slower drivers or worn tyres increase incident chances
        incident = None
        time_loss = 0.0

        # Check for incident if not behind safety car
        is_safety_car = race_state.safety_car_deployed
        is_vsc = race_state.vsc_active

        if not is_safety_car and not is_vsc:
            incident = self.incident_model.generate_incident(
                driver=driver,
                car=car,
                track=track,
                weather=weather.condition,
                lap=lap_number,
                sector=rng.integers(1, 4),
                tyre_wear=driver_state.tyre_wear,
                in_traffic=driver_state.in_traffic,
                rng=rng,
            )

            if incident:
                # If retirement, mark state
                if incident.severity == IncidentSeverity.TERMINAL:
                    driver_state.status = "retired"
                    driver_state.dnf_reason = incident.retirement_reason
                else:
                    time_loss = incident.time_loss
                    # Apply damage
                    driver_state.aero_damage = min(1.0, driver_state.aero_damage + incident.aero_damage)  # noqa: E501
                    driver_state.engine_damage = min(1.0, driver_state.engine_damage + incident.mechanical_damage)  # noqa: E501

                    # Flatspot tyres on lockup
                    if incident.incident_type == IncidentType.LOCKUP:
                        # Create temporary TyreState to flatspot
                        from app.simulation.models.tyre import TyreState as ModelTyreState
                        tyre_state = ModelTyreState(
                            compound=driver_state.tyre_compound,
                            set_id=f"set_{driver.id}_{driver_state.tyre_age}",
                            age_laps=driver_state.tyre_age,
                            wear=driver_state.tyre_wear,
                            temp_fl=driver_state.tyre_temp,
                            temp_fr=driver_state.tyre_temp,
                            temp_rl=driver_state.tyre_temp,
                            temp_rr=driver_state.tyre_temp,
                        )
                        tyre_state = self.tyre_physics_model.simulate_lockup(tyre_state, rng)
                        driver_state.tyre_wear = tyre_state.wear

        # 4. Prepare inputs for LapTimeModel
        driver_effective_skill = driver.get_effective_skill(
            track_id=track.id,
            weather=weather.condition,
            session_type="qualifying" if is_qualifying else "race",
            pressure=1.0 if driver_state.gap_ahead < 1.0 or driver_state.gap_behind < 1.0 else 0.0,
        )

        # Determine engine mode power
        engine_mode = EngineMode.STANDARD
        if is_qualifying:
            engine_mode = EngineMode.QUALIFYING
        elif driver_state.ers_mode == "overtake":
            engine_mode = EngineMode.OVERTAKE
        elif driver_state.ers_mode == "high":
            engine_mode = EngineMode.ATTACK
        elif driver_state.ers_mode == "low":
            engine_mode = EngineMode.CONSERVE

        # Get current engine power
        # Fetch or mock engine
        engine_power = 780.0  # nominal

        lap_inputs = LapTimeInputs(
            base_lap_time=track.reference_lap_time,
            car=car,
            engine_power_kw=engine_power,
            driver=driver,
            driver_effective_skill=driver_effective_skill,
            compound=driver_state.tyre_compound,
            tyre_spec=tyre_spec,
            tyre_age_laps=driver_state.tyre_age,
            tyre_wear=driver_state.tyre_wear,
            tyre_temp=driver_state.tyre_temp,
            fuel_mass=driver_state.fuel_mass,
            fuel_per_lap=driver_state.fuel_burn_rate,
            track=track,
            track_evolution=race_state.track_evolution,
            track_grip=track_grip,
            weather=weather,
            is_qualifying=is_qualifying,
            is_race_start=is_race_start,
            is_safety_car=is_safety_car,
            is_vsc=is_vsc,
            drs_active=drs_active,
            ers_mode=driver_state.ers_mode,
            in_traffic=driver_state.in_traffic,
            traffic_loss=driver_state.traffic_loss,
            aero_damage=driver_state.aero_damage,
            mechanical_damage=driver_state.engine_damage,
            rng=rng,
        )

        # 5. Calculate lap time components
        components = self.lap_time_model.calculate_lap_time(lap_inputs)

        # Add incident time loss
        lap_time = components.total + time_loss

        # If under Safety Car, cap pace to SC pace
        if is_safety_car:
            # SC pace is roughly 1.4x reference pace
            lap_time = max(track.reference_lap_time * 1.35, lap_time)
        elif is_vsc:
            # VSC pace is roughly 1.3x reference pace
            lap_time = max(track.reference_lap_time * 1.25, lap_time)

        # 6. Split into sector times
        sector_times = track.get_sector_times(lap_time)

        # 7. Evolve Tyre and Fuel States
        # Prepare Tyre Physics Inputs
        from app.simulation.models.tyre import TyreState as ModelTyreState
        current_tyre_state = ModelTyreState(
            compound=driver_state.tyre_compound,
            set_id=f"set_{driver.id}_{driver_state.tyre_age}",
            age_laps=driver_state.tyre_age,
            wear=driver_state.tyre_wear,
            temp_fl=driver_state.tyre_temp,
            temp_fr=driver_state.tyre_temp,
            temp_rl=driver_state.tyre_temp,
            temp_rr=driver_state.tyre_temp,
        )

        tyre_inputs = TyrePhysicsInputs(
            compound=driver_state.tyre_compound,
            spec=tyre_spec,
            state=current_tyre_state,
            car=car,
            track=track,
            weather=weather,
            track_temp=weather.track_temperature,
            track_wetness=weather.track_wetness,
            fuel_mass=driver_state.fuel_mass,
            is_pushing=driver_state.ers_mode in ("overtake", "high"),
            is_cooling=driver_state.ers_mode == "low",
            in_traffic=driver_state.in_traffic,
            lap_number=lap_number,
            stint_lap=driver_state.tyre_age,
            rng=rng,
        )

        # Step tyre physics
        new_tyre_state = self.tyre_physics_model.step(tyre_inputs)

        # Update driver state with new tyre values
        driver_state.tyre_age = new_tyre_state.age_laps
        driver_state.tyre_wear = new_tyre_state.wear
        driver_state.tyre_temp = new_tyre_state.avg_temp

        # Fuel consumption
        # Fuel burns off every lap
        fuel_consumed = driver_state.fuel_burn_rate
        if is_safety_car or is_vsc:
            fuel_consumed *= 0.6  # Save fuel under SC/VSC
        driver_state.fuel_mass = max(0.1, driver_state.fuel_mass - fuel_consumed)

        # Update driver state stats
        driver_state.lap = lap_number
        driver_state.total_time += lap_time
        driver_state.last_lap_time = lap_time
        if driver_state.best_lap_time is None or lap_time < driver_state.best_lap_time:
            driver_state.best_lap_time = lap_time
        driver_state.sector_times = sector_times

        return LapResult(
            driver_id=driver.id,
            lap_number=lap_number,
            lap_time=lap_time,
            sector_times=sector_times,
            tyre_wear=driver_state.tyre_wear,
            tyre_temp=driver_state.tyre_temp,
            tyre_age=driver_state.tyre_age,
            fuel_remaining=driver_state.fuel_mass,
            incident=incident,
            time_loss=time_loss,
            components=components,
        )
