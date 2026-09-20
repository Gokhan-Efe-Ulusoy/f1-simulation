from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.simulation.calibration import CalibrationProfile
from app.simulation.core.events import (
    create_battle_ended_event,
    create_battle_side_by_side_event,
    create_battle_started_event,
    create_battle_updated_event,
    create_defense_action_event,
    create_drs_train_formed_event,
    create_drying_line_event,
    create_ers_mode_changed_event,
    create_first_corner_completed_event,
    create_formation_lap_completed_event,
    create_formation_lap_started_event,
    create_lap_completed_event,
    create_overtake_attempted_event,
    create_overtake_completed_event,
    create_overtake_failed_event,
    create_overtake_opportunity_event,
    create_race_started_event,
    create_rain_intensity_changed_event,
    create_red_flag_deployed_event,
    create_red_flag_lifted_event,
    create_safety_car_restarted_event,
    create_sector_completed_event,
    create_sector_incident_event,
    create_sector_overtake_opportunity_event,
    create_standing_restart_event,
    create_start_completed_event,
    create_team_order_executed_event,
    create_team_order_issued_event,
    create_track_wetness_changed_event,
    create_tyre_crossover_event,
)
from app.simulation.core.lap_simulator import LapSimulator
from app.simulation.core.random import RandomProvider
from app.simulation.core.state import (
    DriverResult,
    DriverState,
    DriverStatus,
    EventVerbosity,
    RaceResult,
    RaceState,
    SessionType,
    SimulationConfig,
    TelemetrySampling,
)
from app.simulation.environment import (
    ForecastUncertainty,
    TrackOvertakeMap,
    TrackWetnessModel,
    TyreCrossoverModel,
    get_overtake_map_for_track,
)
from app.simulation.models.car import Car, Engine
from app.simulation.models.driver import Driver
from app.simulation.models.strategy import RaceStrategy, StrategyType
from app.simulation.models.track import Track
from app.simulation.models.tyre import TyreCompound, get_standard_tyre_specs
from app.simulation.models.weather import create_weather_model
from app.simulation.racing import (
    BattleContext,
    BattleEngine,
    BattlePlanner,
    BattleResourceState,
    BattleStateType,
    DefenseContext,
    DefenseModel,
    DirtyAirContext,
    DirtyAirModel,
    DRSTrainContext,
    DRSTrainModel,
    FirstCornerModel,
    FormationLapModel,
    OvertakeContext,
    OvertakeEngine,
    RedFlagConfig,
    RedFlagModel,
    SafetyCarRestartContext,
    SafetyCarRestartModel,
    StandingRestartModel,
    StandingStartModel,
)
from app.simulation.strategy import (
    FuelStrategyOptimizer,
    LiveStrategyAdvisor,
    PitStopStrategyEngine,
    StrategyContext,
    StrategyEngine,
)
from app.simulation.strategy.team_orders import (
    TeamOrderModel,
)
from app.simulation.telemetry import TelemetrySampler
from app.simulation.version import CONFIG_VERSION, MODEL_VERSION, SIMULATION_VERSION


class RaceEngine(BaseModel):
    """Full race simulation engine."""

    lap_simulator: LapSimulator = LapSimulator()
    strategy_engine: StrategyEngine | None = None
    fuel_optimizer: FuelStrategyOptimizer | None = None
    pit_strategy_engine: PitStopStrategyEngine | None = None
    strategy_advisor: LiveStrategyAdvisor | None = None

    # Racing dynamics components
    overtake_engine: OvertakeEngine | None = None
    battle_engine: BattleEngine | None = None
    dirty_air_model: DirtyAirModel | None = None
    drs_train_model: DRSTrainModel | None = None
    defense_model: DefenseModel | None = None
    safety_car_restart_model: SafetyCarRestartModel | None = None

    # Phase 7: Environment models
    track_wetness_model: TrackWetnessModel | None = None
    tyre_crossover_model: TyreCrossoverModel | None = None
    forecast_model: ForecastUncertainty | None = None
    overtake_map: TrackOvertakeMap | None = None
    team_order_model: TeamOrderModel | None = None

    # Phase 8: race procedure + planning (lazy-initialized, deterministic)
    formation_model: FormationLapModel | None = None
    start_model: StandingStartModel | None = None
    first_corner_model: FirstCornerModel | None = None
    red_flag_model: RedFlagModel | None = None
    standing_restart_model: StandingRestartModel | None = None
    battle_planner: BattlePlanner | None = None

    # Phase 8: caches (per engine instance; cleared per race where needed)
    sector_weight_cache: dict = Field(default_factory=dict)
    calibration: CalibrationProfile | None = None

    # Phase 18: race control (lazy-initialized)
    race_control_engine: Any = Field(default=None)
    race_control_state: Any = Field(default=None)
    race_control_counters: dict = Field(default_factory=dict)
    race_control_history: list[dict] = Field(default_factory=list)

    # Phase 19: strategy decision engine
    decision_engine: Any = Field(default=None)
    strategy_state_history: list[dict] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def _emit(
        self,
        events: list[dict],
        config: SimulationConfig,
        event,
        level: str = "standard",
    ) -> None:
        """Append an event honoring verbosity (MINIMAL < STANDARD < FULL).

        STANDARD is the Phase 1-7 default set and stays the default, so
        existing callers see identical output.
        """
        order = {
            EventVerbosity.MINIMAL: 0,
            EventVerbosity.STANDARD: 1,
            EventVerbosity.FULL_TELEMETRY: 2,
        }
        need = {"minimal": 0, "standard": 1, "full": 2}[level]
        have = order.get(config.event_verbosity, 1)
        if have >= need:
            events.append(event.model_dump() if hasattr(event, "model_dump") else event)

    def simulate_race(
        self,
        config: SimulationConfig,
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        rng: RandomProvider,
        engines: dict[str, Engine] | None = None,
    ) -> RaceResult:
        """Run a complete race simulation."""
        # Initialize strategy components
        self._initialize_strategy_components(drivers, cars, track, config, rng)

        # Initialize weather
        weather_model, weather_rng = create_weather_model(
            condition=config.initial_weather,
            air_temp=25.0,
            track_temp=35.0,
            humidity=60.0,
            volatility=config.weather_variability,
            seed=rng.integers(0, 2**31 - 1),
        )

        # Initialize race state
        initial_weather = weather_model.initial_state
        race_state = RaceState(
            current_lap=0,
            total_laps=config.total_laps,
            race_state="not_started",
            weather_condition=initial_weather.condition,
            track_evolution=0.0,
        )
        current_weather_state = initial_weather

        # Initialize driver states
        driver_states = self._initialize_driver_states(drivers, cars, config, track)

        # Grid order
        grid_order = self._determine_grid_order(drivers, cars, track, rng)

        for i, driver_id in enumerate(grid_order):
            driver_states[driver_id].position = i + 1
            if i == 0:
                driver_states[driver_id].gap_ahead = 0.0
            else:
                driver_states[driver_id].gap_ahead = rng.uniform(0.2, 0.8)

        events: list[dict] = []

        race_start_event = create_race_started_event(
            timestamp=0.0,
            total_laps=config.total_laps,
            drivers=grid_order,
        )
        events.append(race_start_event.model_dump())

        # Phase 8: per-race isolation + telemetry sampler
        if self.battle_engine is not None:
            self.battle_engine.reset()
        self.sector_weight_cache = {}
        sampler = TelemetrySampler(config.telemetry_sampling)
        red_flag_laps_remaining = 0

        # Phase 8: formation lap + standing start + first corner
        self._run_formation_and_start(
            driver_states, drivers, cars, track, config, rng, events, grid_order
        )

        race_state.race_state = "green"
        race_state.current_lap = 1

        self._update_gaps(race_state, driver_states, grid_order)

        # Initialize strategies for each driver
        driver_strategies = self._initialize_driver_strategies(
            drivers, cars, engines, track, config, grid_order, driver_states, rng
        )

        # Main race loop
        prev_terminal_incident = False
        # Phase 18 race-control sequential state
        rc_consec_wet = 0
        prev_incident_severity = None
        prev_incident_is_ret = False
        prev_incident_block = False
        rc_restart_laps_remaining = 0  # for DRS gating
        for lap in range(1, config.total_laps + 1):
            race_state.current_lap = lap

            # Phase 18: race-control update (deterministic, precedes weather so weather coupling is via current lap weather)
            # We still keep red-flag suspension logic but now driven via race control state machine when enabled
            if config.race_control_enabled and self.race_control_engine is not None:
                # Update weather first so coupling uses current weather (we need current_weather_state even before step? step after)
                # For sequential path, we evolve weather similarly but rc uses previous lap's weather + current incident
                pass

            # Phase 8: red-flag suspension freezes all progression (kept for backward compat when race_control disabled)
            if red_flag_laps_remaining > 0:
                red_flag_laps_remaining -= 1
                if red_flag_laps_remaining <= 0:
                    self._run_standing_restart(
                        driver_states, drivers, cars, track, lap, config,
                        race_state, current_weather_state, rng, events,
                    )
                    race_state.race_state = "green"
                    if config.race_control_enabled:
                        self.race_control_state = 0
                        rc_restart_laps_remaining = 2
                continue

            # Phase 8: red-flag trigger (before weather so suspension freezes it).
            # Only deploy when the full suspension + restart fits before the
            # finish, so every deploy is always followed by lifted + restart.
            # When race_control_enabled, this is handled via race control engine below, so skip old path
            if not config.race_control_enabled:
                if config.red_flag_probability > 0.0 and lap + config.red_flag_laps < config.total_laps:  # noqa: E501
                    extreme = (
                        current_weather_state.condition.value
                        if hasattr(current_weather_state.condition, "value")
                        else str(current_weather_state.condition)
                    ) == "heavy_rain" and race_state.track_wetness > 0.8
                    assert self.red_flag_model is not None  # initialized pre-race
                    decision = self.red_flag_model.check(
                        lap, prev_terminal_incident, extreme, rng.get_stream("red_flag")
                    )
                    if decision.deploy:
                        red_flag_laps_remaining = config.red_flag_laps
                        race_state.race_state = "red_flag"
                        self._emit(events, config, create_red_flag_deployed_event(
                            timestamp=race_state.current_time, lap=lap,
                            reason=decision.reason, laps_remaining=config.red_flag_laps,
                        ), "minimal")
                        prev_terminal_incident = False
                        continue
                prev_terminal_incident = False

            # Update weather
            current_weather_state = weather_model.step(current_weather_state, lap - 1) if lap > 1 else current_weather_state  # noqa: E501
            race_state.weather_condition = current_weather_state.condition

            # Track weather wetness for race control coupling (use track_wetness)
            # Update rc_consec_wet
            try:
                w_wet = float(getattr(current_weather_state, "track_wetness", 0.0) or 0.0)
            except:
                w_wet = 0.0
            try:
                w_rain = float(getattr(current_weather_state, "rainfall_mm_h", 0.0) or 0.0)
            except:
                w_rain = 0.0
            if w_wet >= 0.5:
                rc_consec_wet += 1
            else:
                rc_consec_wet = 0

            # Phase 18: race-control state transition (when enabled)
            if config.race_control_enabled and self.race_control_engine is not None:
                from app.simulation.race_control.kernels import PHASE_GREEN, PHASE_RESTART, PHASE_SAFETY_CAR, PHASE_VSC, PHASE_RED_FLAG, PHASE_YELLOW, PHASE_DOUBLE_YELLOW  # noqa: E501
                from app.simulation.race_control.models import IncidentSeverity
                # Map prev incident to severity enum
                rc_sev = None
                if prev_incident_severity is not None:
                    try:
                        rc_sev = IncidentSeverity(prev_incident_severity.value) if hasattr(prev_incident_severity, "value") else IncidentSeverity(prev_incident_severity)  # noqa: E501
                    except:
                        rc_sev = None
                    # Normalize terminal -> severe
                    if rc_sev and str(rc_sev).lower() == "terminal":
                        rc_sev = IncidentSeverity.SEVERE
                # Lap 1 first-lap handling already via prev_incident
                vis = 0.5 if w_wet > 0.8 else 1.0
                new_phase, self.race_control_counters = self.race_control_engine.next_state(
                    current_phase=int(self.race_control_state),
                    lap=lap,
                    rng=rng.get_stream("race_control") if hasattr(rng, "get_stream") else rng._rng,
                    weather_wetness=w_wet,
                    rainfall=w_rain,
                    visibility=vis,
                    incident_severity=rc_sev,
                    incident_is_retirement=prev_incident_is_ret,
                    incident_causes_blockage=prev_incident_block,
                    consec_wet_laps=rc_consec_wet,
                    counters=self.race_control_counters,
                )
                # Detect transitions for events/compression
                old_phase = int(self.race_control_state)
                self.race_control_state = new_phase
                self.race_control_history.append({"lap": lap, "from": old_phase, "to": new_phase})
                # Map int to string for RaceState
                phase_to_str = {0: "green", 1: "yellow", 2: "yellow", 3: "vsc", 4: "safety_car", 5: "red_flag", 6: "formation", 7: "start", 8: "green", 9: "finished", 10: "red_flag", 11: "green"}  # noqa: E501
                race_state.race_state = phase_to_str.get(new_phase, "green")
                # Sync legacy flags
                race_state.safety_car_deployed = (new_phase == PHASE_SAFETY_CAR)
                race_state.vsc_active = (new_phase == PHASE_VSC)
                # Red flag suspension handling (Phase 18 style)
                if new_phase == PHASE_RED_FLAG:
                    red_flag_laps_remaining = self.race_control_engine.policy.red_flag_duration_laps[0]  # at least 3?  # noqa: E501
                    try:
                        # sample deterministic
                        red_flag_laps_remaining = int(rng.get_stream("race_control").integers(self.race_control_engine.policy.red_flag_duration_laps[0], self.race_control_engine.policy.red_flag_duration_laps[1] + 1))  # noqa: E501
                    except:
                        pass
                    self._emit(events, config, create_red_flag_deployed_event(timestamp=race_state.current_time, lap=lap, reason="race_control", laps_remaining=red_flag_laps_remaining), "minimal")  # noqa: E501
                    prev_incident_severity = None
                    prev_incident_is_ret = False
                    prev_incident_block = False
                    continue
                if new_phase == PHASE_RESTART:
                    self._handle_safety_car_restart(driver_states, drivers, cars, track, lap, config, race_state, current_weather_state, rng, events)  # noqa: E501
                    rc_restart_laps_remaining = 2
                    # next lap will go green via engine
                # Decrement restart DRS lock
                if rc_restart_laps_remaining > 0:
                    rc_restart_laps_remaining -= 1
                # reset prev incident for next lap after consumed
                prev_incident_severity = None
                prev_incident_is_ret = False
                prev_incident_block = False
            else:
                # legacy safety car handling when race_control disabled
                # Update track evolution only here? Keep shared
                pass

            # Update track evolution
            active_count = len([d for d in driver_states.values() if d.status == "active"])
            race_state.track_evolution += track.get_track_evolution_per_lap(active_count)

            # Check for Safety Car / VSC (legacy path when race_control disabled)
            if not config.race_control_enabled:
                sc_deployed = self._check_safety_car(race_state, lap, rng)
                vsc_deployed = self._check_vsc(race_state, lap, rng)

                if sc_deployed and not race_state.safety_car_deployed:
                    race_state.safety_car_deployed = True
                    race_state.race_state = "safety_car"
                    race_state.safety_car_lap = lap
                    leader = next((d for d in driver_states.values() if d.position == 1), None)
                    race_state.leader_gap_at_sc = leader.gap_ahead if leader else 0.0

                elif race_state.safety_car_deployed and race_state.safety_car_laps_remaining <= 0:
                    # Safety car restart
                    self._handle_safety_car_restart(
                        driver_states, drivers, cars, track, lap, config,
                        race_state, current_weather_state, rng, events
                    )
                    race_state.safety_car_deployed = False
                    race_state.race_state = "green"

                if vsc_deployed and not race_state.vsc_active:
                    race_state.vsc_active = True
                    race_state.race_state = "vsc"
                elif race_state.vsc_active and rng.random() < 0.2:
                    race_state.vsc_active = False
                    race_state.race_state = "green"

            # Determine driving order
            driving_order = self._get_driving_order(driver_states)

            # Phase 18: per-lap worst incident tracker for race-control propagation (module-local)
            lap_worst_sev = None
            lap_has_ret = False
            lap_has_block = False

            # Simulate lap for each driver
            for driver_id in driving_order:
                driver_state = driver_states[driver_id]

                if driver_state.status != DriverStatus.ACTIVE:
                    continue

                driver = next(d for d in drivers if d.id == driver_id)
                car = cars[driver_id]

                race_state.track_evolution += track.get_track_evolution_per_lap(1) * 0.1

                # Determine DRS
                drs_active = self._check_drs_availability(driver_state, race_state)

                # Determine ERS mode
                ers_mode = self._determine_ers_mode(driver_state)

                # Simulate lap
                lap_result = self.lap_simulator.simulate_lap(
                    lap_number=lap,
                    driver=driver,
                    car=car,
                    driver_state=driver_state,
                    race_state=race_state,
                    track=track,
                    weather=current_weather_state,
                    rng=rng,
                    is_race_start=(lap == 1),
                    drs_active=driver_state.drs_active,
                )

                # Handle incidents + propagate to race control (causal chain)
                if lap_result.incident:
                    sev = lap_result.incident.severity
                    # Map terminal -> severe for policy
                    sev_str = sev.value if hasattr(sev, "value") else str(sev)
                    if sev_str == "terminal":
                        lap_worst_sev = sev  # will be mapped to SEVERE downstream
                        lap_has_ret = True
                        lap_has_block = True
                    else:
                        # choose worst across drivers via priority
                        priority = {"minor": 1, "moderate": 2, "major": 3, "severe": 4, "terminal": 4}  # noqa: E501
                        cur_p = priority.get(str(lap_worst_sev).lower() if lap_worst_sev else "minor", 0)  # noqa: E501
                        new_p = priority.get(sev_str.lower(), 0)
                        if lap_worst_sev is None or new_p > cur_p:
                            lap_worst_sev = sev
                        if lap_result.incident.is_retirement:
                            lap_has_ret = True
                        # block if collision/track_blockage shape? approximated via severity major+
                        if sev_str in ("major", "severe", "terminal"):
                            if lap_result.incident.incident_type and str(lap_result.incident.incident_type).lower() in ("collision", "track_blockage", "stopped_car", "obstruction"):  # noqa: E501
                                lap_has_block = True
                            elif sev_str in ("major", "terminal"):
                                lap_has_block = True

                if lap_result.incident and lap_result.incident.severity == "terminal":
                    driver_state.status = DriverStatus.RETIRED
                    driver_state.dnf_reason = lap_result.incident.retirement_reason
                    prev_terminal_incident = True
                    continue

                # Phase 8: per-sector breakdown (exact partition of lap time)
                # + sector incident check (gated by incident_probability) + telemetry
                self._process_driver_sectors(
                    driver_state, driver, car, track, lap, config,
                    race_state, current_weather_state, rng, sampler, lap_result,
                    events,
                )

            # Update positions and gaps
            self._update_positions_after_lap(driver_states, grid_order)
            self._update_gaps(race_state, driver_states, grid_order)

            # Phase 18: field compression under SC/VSC (sequential gap dynamics)
            if config.race_control_enabled and self.race_control_state in (4, 3):  # SC=4, VSC=3
                # Compress gaps progressively: move each gap toward 0.7s
                sorted_active = sorted([ds for ds in driver_states.values() if ds.status == DriverStatus.ACTIVE], key=lambda x: x.total_time)  # noqa: E501
                if sorted_active:
                    leader_time = sorted_active[0].total_time
                    target = 0.7
                    rate = 0.55 if self.race_control_state == 4 else 0.25
                    for idx, ds in enumerate(sorted_active):
                        if idx == 0:
                            continue
                        gap = ds.total_time - leader_time
                        new_gap = gap * (1 - rate) + target * rate
                        # Adjust total_time to achieve new gap (keep leader fixed)
                        ds.total_time = leader_time + new_gap
                    # Re-sort after compression
                    self._update_positions_after_lap(driver_states, grid_order)
                    self._update_gaps(race_state, driver_states, grid_order)

            # Propagate incident to race-control for NEXT lap
            if lap_worst_sev is not None:
                prev_incident_severity = lap_worst_sev
                prev_incident_is_ret = lap_has_ret
                prev_incident_block = lap_has_block
            else:
                # Keep None unless new incident
                pass

            # Process racing dynamics (overtakes, battles, DRS trains, defense) — suppressed under SC/VSC/RED/RaceSuspended/Yellow
            should_skip_battles = False
            if config.race_control_enabled and self.race_control_state in (1, 2, 3, 4, 5, 10):
                # YELLOW/SC/VSC/RED suppress overtaking (spec: near zero for VSC/SC, reduced for yellow)
                # For determinism and invariants, skip battle engine entirely under full neutralisation,
                # allow minimal reduced battles under yellow is still skipped for now (prior-only)
                if self.race_control_state in (3, 4, 5, 10):
                    should_skip_battles = True
                elif self.race_control_state in (1, 2):
                    # Reduced -> 25% chance to skip? For determinism we skip 75% of yellow laps
                    # Use lap parity deterministic
                    should_skip_battles = (lap % 4 != 0)
            if not should_skip_battles:
                self._process_racing_dynamics(
                    driver_states, drivers, cars, track, lap, config,
                    race_state, current_weather_state, rng, events,
                    sampler=sampler,
                )

            # Handle pit stops with strategy
            self._handle_pit_stops_with_strategy(
                driver_states, cars, track, lap, config, rng,
                driver_strategies, race_state, current_weather_state
            )

            race_state.weather_condition = current_weather_state.condition

            # Lap completed event
            lap_event = create_lap_completed_event(
                timestamp=sum(ds.total_time for ds in driver_states.values() if ds.status == DriverStatus.ACTIVE) / max(1, len([d for d in driver_states.values() if d.status == DriverStatus.ACTIVE])),  # noqa: E501
                lap=lap,
                driver_id="all",
                position=1,
                lap_time=0,
                sector_times=[],
                tyre_compound="",
                tyre_age=0,
                fuel_mass=0,
            )

        race_state.race_state = "finished"

        results = self._compile_results(
            config, drivers, cars, driver_states, track, lap, events, rng,
            telemetry=sampler.to_dicts(),
        )

        return results

    def _run_formation_and_start(
        self,
        driver_states: dict[str, DriverState],
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        config: SimulationConfig,
        rng: RandomProvider,
        events: list[dict],
        grid_order: list[str],
    ) -> None:
        """Phase 8: formation lap, standing start, first-corner phase."""
        assert self.formation_model is not None
        assert self.start_model is not None
        assert self.first_corner_model is not None
        self._emit(events, config, create_formation_lap_started_event(
            timestamp=0.0, lap=0, drivers=list(grid_order)), "minimal")
        ready, failed = [], []
        allow_incidents = config.incident_probability > 0.0
        for driver_id in grid_order:
            state = driver_states[driver_id]
            driver = next(d for d in drivers if d.id == driver_id)
            car = cars.get(driver_id)
            reliability = getattr(car, "chassis_reliability", 90.0) if car else 90.0
            res = self.formation_model.run(
                driver_id, state.tyre_temp, driver.aggression,
                reliability, rng.get_stream("formation"))
            state.tyre_temp = res.tyre_temp
            if res.incident and allow_incidents:
                if res.failed_to_start:
                    state.status = DriverStatus.RETIRED
                    state.dnf_reason = "failed_to_start"
                    failed.append(driver_id)
                    continue
                state.total_time += 2.0
            ready.append(driver_id)
        self._emit(events, config, create_formation_lap_completed_event(
            timestamp=0.0, lap=0, ready_drivers=ready,
            failed_drivers=failed), "minimal")

        # Standing start (time deltas only; order resolved by lap-1 pace)
        grip = 1.0
        for driver_id in grid_order:
            start_state = driver_states.get(driver_id)
            if start_state is None or start_state.status != DriverStatus.ACTIVE:
                continue
            state = start_state
            driver = next(d for d in drivers if d.id == driver_id)
            car = cars.get(driver_id)
            start = self.start_model.evaluate(
                driver_id,
                start_performance=driver.start_performance,
                aggression=driver.aggression,
                car_traction=getattr(car, "traction", 75.0) if car else 75.0,
                car_power_proxy=getattr(car, "drs_effectiveness", 75.0) if car else 75.0,
                tyre_temp=state.tyre_temp,
                track_grip=grip,
                rng=rng.get_stream("start"),
            )
            delta = (start.reaction_time - 0.25) + (0.5 - start.launch_quality) * 0.3
            # Pre-race totals must never go negative (a fully suspended race
            # would otherwise report impossible negative race times).
            state.total_time = max(0.0, state.total_time + delta)
            self._emit(events, config, create_start_completed_event(
                timestamp=0.0, lap=0, driver_id=driver_id,
                reaction_time=start.reaction_time,
                launch_quality=start.launch_quality,
                position_delta=start.position_delta), "minimal")

        # First corner (swaps/time loss only when incidents enabled)
        if config.incident_probability > 0.0:
            n_cars = len([s for s in driver_states.values()
                          if s.status == DriverStatus.ACTIVE])
            braking = float(getattr(track, "braking_energy", 50.0))
            weather_str = (config.initial_weather.value
                           if hasattr(config.initial_weather, "value")
                           else str(config.initial_weather))
            for driver_id in grid_order:
                corner_state = driver_states.get(driver_id)
                if corner_state is None or corner_state.status != DriverStatus.ACTIVE:
                    continue
                state = corner_state
                driver = next(d for d in drivers if d.id == driver_id)
                outcome = self.first_corner_model.evaluate(
                    driver_id, state.position, n_cars, driver.aggression,
                    driver.pressure_resistance, braking, weather_str,
                    rng.get_stream("start"))
                if outcome.outcome == "dnf":
                    state.status = DriverStatus.RETIRED
                    state.dnf_reason = "first_corner_contact"
                elif outcome.outcome != "clean":
                    state.total_time += outcome.time_loss + outcome.positions_lost * 1.2
                    state.aero_damage = min(1.0, state.aero_damage + 0.1)
                self._emit(events, config, create_first_corner_completed_event(
                    timestamp=0.0, lap=1, driver_id=driver_id,
                    outcome=outcome.outcome, time_loss=outcome.time_loss,
                    positions_lost=outcome.positions_lost), "minimal")

    def _run_standing_restart(
        self,
        driver_states: dict[str, DriverState],
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        lap: int,
        config: SimulationConfig,
        race_state: RaceState,
        weather_state,
        rng: RandomProvider,
        events: list[dict],
    ) -> None:
        """Phase 8: standing restart after a red flag (SC-model reuse)."""
        assert self.standing_restart_model is not None
        active = [ds for ds in driver_states.values() if ds.status == DriverStatus.ACTIVE]
        if not active:
            return
        timestamp = sum(ds.total_time for ds in active) / len(active)
        order = sorted(active, key=lambda s: s.position)
        for state in order:
            driver = next(d for d in drivers if d.id == state.driver_id)
            from app.simulation.racing.models import SafetyCarRestartContext as _SCRC

            ctx = _SCRC(
                driver_id=state.driver_id, position=state.position,
                gap_to_ahead=state.gap_ahead,
                tyre_compound=state.tyre_compound.value
                if hasattr(state.tyre_compound, "value") else str(state.tyre_compound),
                tyre_age=state.tyre_age, tyre_temp=state.tyre_temp,
                start_performance=driver.start_performance,
                pressure_resistance=driver.pressure_resistance,
                aggression=driver.aggression, consistency=driver.consistency,
                weather=str(race_state.weather_condition),
                track_wetness=race_state.track_wetness, track_temp=35.0,
                laps_under_sc=0, is_leader=(state.position == 1),
            )
            res = self.standing_restart_model.evaluate(ctx, rng.get_stream("restart"))
            state.total_time += res.reaction_time * 0.1
        leader = next((s for s in order if s.position == 1), order[0])
        self._emit(events, config, create_standing_restart_event(
            timestamp=timestamp, lap=lap, leader_id=leader.driver_id,
            field_compressed=True), "minimal")
        self._emit(events, config, create_red_flag_lifted_event(
            timestamp=timestamp, lap=lap,
            laps_suspended=config.red_flag_laps), "minimal")

    def _process_driver_sectors(
        self,
        driver_state: DriverState,
        driver: Driver,
        car: Car,
        track: Track,
        lap: int,
        config: SimulationConfig,
        race_state: RaceState,
        weather_state,
        rng: RandomProvider,
        sampler: TelemetrySampler,
        lap_result,
        events: list[dict],
    ) -> None:
        """Phase 8: exact sector partition + sector incident + telemetry."""
        from app.simulation.racing.sectors import (
            compute_sector_weights,
            split_lap_into_sectors,
        )

        cache_key = (track.id, car.id, driver.id)
        weights = self.sector_weight_cache.get(cache_key)
        if weights is None:
            weights = compute_sector_weights(track, car, driver)
            self.sector_weight_cache[cache_key] = weights
        sector_times = split_lap_into_sectors(lap_result.lap_time, weights)
        driver_state.sector_times = sector_times
        driver_state.current_sector = len(sector_times) - 1

        # Sector incident (only when incidents enabled; keeps invariant)
        if config.incident_probability > 0.0:
            s_rng = rng.get_stream("sector")
            n = len(sector_times)
            per_sector_p = min(0.05, config.incident_probability / max(1, n))
            for s_idx in range(n):
                if s_rng.random() < per_sector_p:
                    loss = 1.0 + s_rng.random() * 4.0
                    sector_times[s_idx] += loss
                    driver_state.total_time += loss
                    lap_result.lap_time += loss
                    if driver_state.last_lap_time is not None:
                        driver_state.last_lap_time += loss
                    self._emit(events, config,
                               create_sector_incident_event(
                                   timestamp=driver_state.total_time, lap=lap,
                                   driver_id=driver_state.driver_id, sector=s_idx,
                                   incident_type="off_track", time_loss=loss),
                               "full")
                    break
            driver_state.sector_times = sector_times

        # Telemetry sampling
        if sampler.sampling != TelemetrySampling.OFF:
            lengths = list(getattr(track, "sector_lengths_km", []) or [])
            for s_idx, s_time in enumerate(sector_times):
                dist = lengths[s_idx] if s_idx < len(lengths) else 0.0
                sampler.record_sector(
                    lap=lap, sector=s_idx, driver_id=driver_state.driver_id,
                    position=driver_state.position, gap_ahead=driver_state.gap_ahead,
                    sector_time=s_time, sector_distance_km=dist,
                    driver_state=driver_state,
                    track_wetness=race_state.track_wetness,
                )
            if sampler.sampling in (TelemetrySampling.LAP, TelemetrySampling.FULL):
                sampler.record_lap(
                    lap=lap, driver_id=driver_state.driver_id,
                    position=driver_state.position, gap_ahead=driver_state.gap_ahead,
                    lap_time=lap_result.lap_time, driver_state=driver_state,
                    track_wetness=race_state.track_wetness,
                )

    def _initialize_strategy_components(
        self,
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        config: SimulationConfig,
        rng: RandomProvider,
    ):
        """Initialize strategy engines and racing dynamics components."""
        if self.strategy_engine is None:
            self.strategy_engine = StrategyEngine()
        if self.fuel_optimizer is None:
            self.fuel_optimizer = FuelStrategyOptimizer(
                base_fuel_consumption=1.8,
                fuel_tank_capacity=config.max_fuel_kg if hasattr(config, 'max_fuel_kg') else 110.0,
            )
        if self.pit_strategy_engine is None:
            self.pit_strategy_engine = PitStopStrategyEngine()

        # Initialize racing dynamics components
        if self.overtake_engine is None:
            self.overtake_engine = OvertakeEngine()
        if self.battle_engine is None:
            self.battle_engine = BattleEngine(overtake_engine=self.overtake_engine)
        if self.dirty_air_model is None:
            self.dirty_air_model = DirtyAirModel()
        if self.drs_train_model is None:
            self.drs_train_model = DRSTrainModel()
        if self.defense_model is None:
            self.defense_model = DefenseModel()
        if self.safety_car_restart_model is None:
            self.safety_car_restart_model = SafetyCarRestartModel()

        # Phase 7: Initialize environment models (deterministic streams)
        if self.track_wetness_model is None:
            self.track_wetness_model = TrackWetnessModel(
                base_drying_rate=config.drying_rate_base,
                racing_line_drying_multiplier=config.racing_line_drying_multiplier,
                rain_accumulation_rate=config.wetness_accumulation_rate,
            )
            self.track_wetness_model.initialize(track, rng.get_stream("drying_line"))
        if self.tyre_crossover_model is None:
            self.tyre_crossover_model = TyreCrossoverModel(
                slick_to_intermediate_threshold=config.intermediate_crossover_threshold,
                intermediate_to_slick_threshold=config.slick_crossover_threshold,
            )
        if self.forecast_model is None:
            weather_model, _ = create_weather_model(
                condition=config.initial_weather,
                air_temp=25.0,
                track_temp=35.0,
                humidity=60.0,
                volatility=config.weather_variability,
                seed=rng.seed,
            )
            base_forecast = weather_model.generate_forecast(config.total_laps)
            f_rng = rng.get_stream("forecast")
            noisy_laps: list[dict] = []
            for wf in base_forecast.lap_forecasts:
                noisy_laps.append({
                    "precipitation_rate": max(
                        0.0,
                        float(wf.precipitation_rate)
                        + float(f_rng.normal(0, config.forecast_error_sigma)),
                    ),
                    "confidence": 1.0,
                })
            self.forecast_model = ForecastUncertainty(
                lap_forecasts=noisy_laps,
                rain_probability=base_forecast.rain_probability,
                max_precipitation=base_forecast.max_precipitation,
                temperature_range=base_forecast.temperature_range,
                forecast_error_sigma=config.forecast_error_sigma,
            )
        if self.overtake_map is None:
            self.overtake_map = get_overtake_map_for_track(track.id)
        if self.team_order_model is None:
            from app.simulation.strategy.team_orders import TeamOrderModel as _TOM

            self.team_order_model = _TOM()

        # Phase 8: procedure + planning components (no RNG draws here)
        if self.formation_model is None:
            self.formation_model = FormationLapModel()
        if self.start_model is None:
            self.start_model = StandingStartModel()
        if self.first_corner_model is None:
            self.first_corner_model = FirstCornerModel()
        if self.red_flag_model is None:
            self.red_flag_model = RedFlagModel(RedFlagConfig(
                base_probability_per_lap=config.red_flag_probability,
                suspension_laps=config.red_flag_laps,
            ))
        if self.standing_restart_model is None:
            self.standing_restart_model = StandingRestartModel(
                restart_model=self.safety_car_restart_model
            )
        if self.battle_planner is None:
            from app.simulation.racing.battle_planner import BattlePlanner as _BP

            self.battle_planner = _BP()
        if self.calibration is None:
            self.calibration = CalibrationProfile()

        # Phase 18: race control engine
        if self.race_control_engine is None:
            from app.simulation.race_control.engine import RaceControlEngine
            from app.simulation.race_control.policy import RaceControlPolicy

            policy = RaceControlPolicy()
            self.race_control_engine = RaceControlEngine(
                policy=policy,
                seed=rng.seed if rng.seed is not None else 42,
                race_id=track.id,
                enable_yellow=config.enable_yellow_flags,
                enable_vsc=config.enable_vsc,
                enable_safety_car=config.enable_safety_car,
                enable_red_flag=config.enable_red_flag,
                enable_first_lap_incidents=config.enable_first_lap_incidents,
                weather_coupling=config.weather_event_coupling,
            )
            self.race_control_state = 0  # PHASE_GREEN int
            self.race_control_counters = {"sc": 0, "vsc": 0, "yellow": 0, "double": 0, "red": 0}
            self.race_control_history = []

        # Phase 19: strategy decision engine (leakage-safe, isolated RNG 700)
        if self.decision_engine is None and config.strategy_enabled:
            from app.simulation.strategy.decision_engine import DecisionEngine

            # Pass as_of for leakage-safe calibration
            as_of = getattr(config, "as_of", None)  # not present; use rng seed based fallback
            # Try to get as_of from track? use generic
            self.decision_engine = DecisionEngine(as_of="2024-03-01" if rng.seed else None, seed=rng.seed if rng.seed else 42)  # noqa: E501
            self.strategy_state_history = []

        # Ensure sector characteristics exist (backward compatible)
        track.initialize_sector_characteristics()

    def _initialize_driver_states(
        self,
        drivers: list[Driver],
        cars: dict[str, Car],
        config: SimulationConfig,
        track: Track,
    ) -> dict[str, DriverState]:
        """Initialize driver states at race start."""
        driver_states = {}

        for driver in drivers:
            car = cars.get(driver.id)
            tyre_specs = get_standard_tyre_specs()

            # Determine starting tyre (based on grid position for race)
            # For now, start on Medium
            starting_compound = TyreCompound.MEDIUM

            driver_state = DriverState(
                driver_id=driver.id,
                position=0,  # Will be set by grid
                lap=0,
                total_time=0.0,
                tyre_compound=starting_compound,
                tyre_age=0,
                tyre_wear=0.0,
                tyre_temp=90.0,
                fuel_mass=config.max_fuel_kg if hasattr(config, 'max_fuel_kg') else 110.0,
                fuel_burn_rate=1.8,
                status=DriverStatus.ACTIVE,
            )
            driver_states[driver.id] = driver_state

        return driver_states

    def _determine_grid_order(
        self,
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        rng: RandomProvider,
    ) -> list[str]:
        """Determine grid order based on qualifying pace."""
        # Simple: sort by combined driver+car performance + small random
        driver_performance = {}
        for driver in drivers:
            car = cars.get(driver.id)
            if not car:
                continue
            qualifying_skill = driver.get_effective_skill(
                track_id="track",
                weather="dry",
                session_type="qualifying"
            )
            car_perf = car.calculate_performance_index("balanced")
            # Add small random for variability
            random_factor = rng.normal(0, 2)  # ±2 performance points
            driver_performance[driver.id] = (qualifying_skill + car_perf) / 2 + random_factor

        # Sort descending (highest performance = P1)
        return sorted(driver_performance.keys(), key=lambda x: driver_performance[x], reverse=True)

    def _update_gaps(self, race_state: RaceState, driver_states: dict[str, DriverState], grid_order: list[str]) -> None:  # noqa: E501
        """Update gap to car ahead/behind for all drivers."""
        sorted_drivers = sorted(
            [ds for ds in driver_states.values() if ds.status == "active"],
            key=lambda x: x.total_time
        )

        for i, ds in enumerate(sorted_drivers):
            if i == 0:
                ds.gap_ahead = 0.0
            else:
                ds.gap_ahead = sorted_drivers[i-1].total_time - ds.total_time

            if i < len(sorted_drivers) - 1:
                ds.gap_behind = sorted_drivers[i+1].total_time - ds.total_time
            else:
                ds.gap_behind = 0.0

    def _get_driving_order(self, driver_states: dict[str, DriverState]) -> list[str]:
        """Get order of drivers for this lap (by position)."""
        active = [ds for ds in driver_states.values() if ds.status == "active"]
        sorted_drivers = sorted(active, key=lambda x: x.position)
        return [ds.driver_id for ds in sorted_drivers]

    def _check_safety_car(self, race_state: RaceState, lap: int, rng: RandomProvider) -> bool:
        """Random chance of safety car."""
        if race_state.safety_car_deployed:
            race_state.safety_car_laps_remaining -= 1
            if race_state.safety_car_laps_remaining <= 0:
                return False
            return True

        # Base probability per lap
        if rng.random() < 0.02:  # 2% chance per lap
            race_state.safety_car_laps_remaining = rng.integers(3, 6)
            return True
        return False

    def _check_vsc(self, race_state: RaceState, lap: int, rng: RandomProvider) -> bool:
        """Random chance of VSC."""
        if race_state.vsc_active:
            if rng.random() < 0.3:
                return False
            return True
        return rng.random() < 0.015  # 1.5% chance per lap

    def _check_drs_availability(self, driver_state: DriverState, race_state: RaceState) -> bool:
        """Check if DRS is available (gap < 1s and DRS zone) with race-control gating."""
        # Base conditions
        base = (
            not driver_state.is_in_pits and
            driver_state.gap_ahead < 1.0 and
            driver_state.gap_ahead > 0 and
            not race_state.safety_car_deployed and
            not race_state.vsc_active
        )
        if not base:
            return False
        # Phase 18: race-control gating
        if hasattr(self, "race_control_state"):
            from app.simulation.race_control.kernels import PHASE_GREEN

            if int(self.race_control_state) != PHASE_GREEN:
                return False
            # Restart DRS lock
            if getattr(self, "race_control_counters", None) and self.race_control_counters.get("_restart_lock", 0) > 0:  # noqa: E501
                return False
        # Additional gating: race_state string
        if race_state.race_state not in ("green", "GREEN"):
            # YELLOW/SC/VSC/RED all disable
            if race_state.race_state in ("yellow", "safety_car", "vsc", "red_flag"):
                return False
        return base

    def _determine_ers_mode(self, driver_state: DriverState) -> str:
        """Simple ERS strategy."""
        if driver_state.gap_ahead < 0.5 and driver_state.gap_ahead > 0:
            return "overtake"
        elif driver_state.gap_behind < 0.5:
            return "high"
        elif driver_state.fuel_mass < 20:
            return "conserve"
        return "medium"

    def _update_positions_after_lap(
        self,
        driver_states: dict[str, DriverState],
        grid_order: list[str]
    ) -> None:
        """Update positions after all drivers complete a lap."""
        # Sort active drivers by total time
        active_drivers = [
            (ds.driver_id, ds.total_time)
            for ds in driver_states.values()
            if ds.status == DriverStatus.ACTIVE
        ]
        active_drivers.sort(key=lambda x: x[1])

        # Retired drivers at the end
        retired_drivers = [ds for ds in driver_states.values() if ds.status == DriverStatus.RETIRED]

        for i, (driver_id, _) in enumerate(active_drivers):
            driver_states[driver_id].position = i + 1

        for i, ds in enumerate(retired_drivers):
            ds.position = len(active_drivers) + i + 1

    def _initialize_driver_strategies(
        self,
        drivers: list[Driver],
        cars: dict[str, Car],
        engines: dict[str, Engine] | None,
        track: Track,
        config: SimulationConfig,
        grid_order: list[str],
        driver_states: dict[str, DriverState],
        rng: RandomProvider,
    ) -> dict[str, RaceStrategy]:
        """Initialize race strategies for all drivers."""
        strategies: dict[str, RaceStrategy] = {}
        for i, driver_id in enumerate(grid_order):
            driver = next(d for d in drivers if d.id == driver_id)
            car = cars[driver_id]
            state = driver_states[driver_id]
            if engines and car.engine_id in engines:
                engine = engines[car.engine_id]
            else:
                engine = Engine(
                    id=car.engine_id or "DEFAULT",
                    name="Default Engine",
                    manufacturer="Generic",
                    supplier_id="GEN",
                    peak_power_kw=780,
                    fuel_burn_rate_base=config.fuel_per_lap,
                )
            position = i + 1
            if position <= 3:
                strategy_type = StrategyType.ONE_STOP if config.total_laps < 50 else StrategyType.TWO_STOP  # noqa: E501
            elif position <= 10:
                strategy_type = StrategyType.TWO_STOP
            else:
                strategy_type = StrategyType.TWO_STOP if config.total_laps > 50 else StrategyType.ONE_STOP  # noqa: E501
            context = StrategyContext(
                track=track,
                car=car,
                engine=engine,
                driver=driver,
                race_laps=config.total_laps,
                pit_lane_time_loss=track.pit_stop_time_loss,
                available_compounds=list(get_standard_tyre_specs().values()),
                starting_compound=state.tyre_compound.value,
                starting_fuel_kg=state.fuel_mass,
                fuel_tank_capacity=110.0,
                team_pit_skill=50.0,
                safety_car_probability=0.15,
            )
            # Fast path for long races: full combinatorial search is exponential
            # in race laps (pre-existing StrategyEngine limitation); use an
            # even-split heuristic. Short races keep the full search.
            if config.total_laps > 10:
                n_stints = 3 if config.total_laps > 50 else 2
                base, rem = divmod(config.total_laps, n_stints)
                stint_laps = [base + (1 if s < rem else 0) for s in range(n_stints)]
                seq = [state.tyre_compound.value]
                for alt in ("hard", "medium", "soft"):
                    if alt != seq[0]:
                        seq.append(alt)
                        break
                while len(seq) < n_stints:
                    seq.append(seq[0])
                heuristic_stops = []
                cum = 0
                for s_idx in range(n_stints - 1):
                    cum += stint_laps[s_idx]
                    heuristic_stops.append({
                        "lap": cum, "compound": seq[s_idx + 1],
                        "stint": s_idx + 1, "reason": "scheduled",
                    })
                strategies[driver_id] = RaceStrategy(
                    driver_id=driver_id,
                    strategy_type=strategy_type,
                    planned_stops=heuristic_stops,
                    starting_compound=state.tyre_compound.value,
                    available_sets={"soft": 3, "medium": 2, "hard": 2},
                    starting_fuel_kg=state.fuel_mass,
                    pit_window_early=3,
                    pit_window_late=5,
                )
                continue
            options = self.strategy_engine.generate_strategy_options(context, max_stops=2)
            if options:
                best_option = self.strategy_engine.rank_strategies(options, context)[0][0]
                planned_stops: list[dict] = []
                cumulative_laps = 0
                for stint_data in best_option.stints[:-1]:
                    cumulative_laps += stint_data["laps"]
                    planned_stops.append({
                        "lap": cumulative_laps,
                        "compound": stint_data["compound"],
                        "stint": len(planned_stops) + 1,
                        "reason": "scheduled",
                    })
                strategies[driver_id] = RaceStrategy(
                    driver_id=driver_id,
                    strategy_type=best_option.strategy_type,
                    planned_stops=planned_stops,
                    starting_compound=state.tyre_compound.value,
                    available_sets={"soft": 3, "medium": 2, "hard": 2},
                    starting_fuel_kg=state.fuel_mass,
                    pit_window_early=3,
                    pit_window_late=5,
                )
        return strategies

    def _handle_pit_stops_with_strategy(
        self,
        driver_states: dict[str, DriverState],
        cars: dict[str, Car],
        track: Track,
        lap: int,
        config: SimulationConfig,
        rng: RandomProvider,
        driver_strategies: dict[str, RaceStrategy],
        race_state: RaceState,
        weather_state,
    ) -> None:
        """Handle pit stops using strategy engine + forecast (no perfect info). Leakage-safe via DecisionEngine when enabled."""  # noqa: E501
        forecast_rain = False
        if self.forecast_model is not None:
            try:
                for ahead in (1, 2):
                    if bool(self.forecast_model.get_rain_probability_at_lap(lap + ahead)):
                        forecast_rain = True
                        break
            except Exception:
                forecast_rain = False

        # Phase 19: use DecisionEngine if strategy_enabled (isolated RNG 700, leakage-safe)
        use_decision_engine = bool(config.strategy_enabled and getattr(self, "decision_engine", None) is not None)  # noqa: E501

        for driver_id, driver_state in driver_states.items():
            if driver_state.status != DriverStatus.ACTIVE:
                continue
            strategy = driver_strategies.get(driver_id)
            if not strategy:
                continue
            competitors = []
            for other_id, other_state in driver_states.items():
                if other_id == driver_id or other_state.status != DriverStatus.ACTIVE:
                    continue
                competitors.append({
                    "driver_id": other_id,
                    "gap_ahead": other_state.total_time - driver_state.total_time,
                    "compound": other_state.tyre_compound.value,
                    "tyre_age": other_state.tyre_age,
                    "fuel_kg": other_state.fuel_mass,
                    "current_lap": lap,
                })

            # Build decision via DecisionEngine when enabled (leakage-safe StrategyState)
            if use_decision_engine:
                try:
                    from app.simulation.strategy.state import build_strategy_state_from_driver

                    # Determine race_control phase string
                    rc_phase = "GREEN"
                    if race_state.safety_car_deployed:
                        rc_phase = "SAFETY_CAR"
                    elif race_state.vsc_active:
                        rc_phase = "VSC"
                    elif race_state.race_state == "red_flag":
                        rc_phase = "RED_FLAG"
                    elif hasattr(self, "race_control_state") and self.race_control_state is not None:  # noqa: E501
                        # Map int phase to string
                        phase_map = {0: "GREEN", 1: "YELLOW", 2: "DOUBLE_YELLOW", 3: "VSC", 4: "SAFETY_CAR", 5: "RED_FLAG", 8: "RESTART"}  # noqa: E501
                        rc_phase = phase_map.get(int(self.race_control_state), "GREEN")
                    # Sector flags (simplified)
                    sector_flags = ["GREEN", "GREEN", "GREEN"]
                    if race_state.race_state in ("yellow", "safety_car", "vsc", "red_flag"):
                        # approximate yellow sector if race not green
                        sector_flags = ["YELLOW", "GREEN", "GREEN"]

                    # Weather regime
                    w_regime = "DRY"
                    wet = float(getattr(race_state, "track_wetness", 0.0) or 0.0)
                    if wet > 0.5:
                        w_regime = "WET"
                    elif wet > 0.1:
                        w_regime = "DAMP"

                    state = build_strategy_state_from_driver(
                        driver_id=driver_id,
                        lap=lap,
                        position=driver_state.position,
                        gap_ahead=driver_state.gap_ahead,
                        gap_behind=driver_state.gap_behind,
                        current_compound=driver_state.tyre_compound.value,
                        tyre_age=driver_state.tyre_age,
                        fuel_remaining=driver_state.fuel_mass,
                        race_control_phase=rc_phase,
                        sector_flags=sector_flags,
                        weather_regime=w_regime,
                        wetness=wet,
                        rainfall=float(getattr(weather_state, "rainfall_mm_h", 0) or 0.0) if weather_state else 0.0,  # noqa: E501
                        track_temperature=float(getattr(weather_state, "track_temperature", 35.0) or 35.0) if weather_state else 35.0,  # noqa: E501
                        forecast_summary={"rain_prob_next_5": 0.15 if forecast_rain else 0.05},
                        pit_loss_estimate=track.pit_stop_time_loss,
                        laps_remaining=config.total_laps - lap,
                        opponent_states=competitors,
                    )
                    dec = self.decision_engine.decide(state, track_pit_loss=track.pit_stop_time_loss, seed=rng.seed if rng.seed else 42, sim_idx=hash(driver_id) % 1000)  # noqa: E501
                    # Map decision to pit boolean
                    should_pit = dec.decision == "PIT"
                    rec_compound = dec.target_compound or driver_state.tyre_compound.value
                    # For logging, store reasoning in events if needed
                    if should_pit:
                        # Perform pit
                        driver_state.is_in_pits = True
                        pit_loss = track.pit_stop_time_loss + rng.normal(0, 0.5)
                        # Apply race-control pit cheap multiplier (from state)
                        if rc_phase == "SAFETY_CAR":
                            pit_loss *= 0.55  # already handled in lap time? but strategy cheap pits still gain  # noqa: E501
                        elif rc_phase == "VSC":
                            pit_loss *= 0.70
                        driver_state.total_time += pit_loss
                        driver_state.tyre_wear = 0.0
                        driver_state.tyre_age = 0
                        driver_state.tyre_temp = 90.0
                        try:
                            driver_state.tyre_compound = TyreCompound(rec_compound)
                        except ValueError:
                            pass
                        driver_state.is_in_pits = False
                        # record history
                        self.strategy_state_history.append({"lap": lap, "driver": driver_id, "decision": dec.model_dump() if hasattr(dec, "model_dump") else str(dec)})  # noqa: E501
                        continue
                    else:
                        # Stay out - ensure we don't also run legacy decision
                        continue
                except Exception:
                    # Fallback to legacy on error
                    pass

            decision = self.pit_strategy_engine.make_pit_decision(
                driver_state={
                    "driver_id": driver_id,
                    "current_lap": lap,
                    "compound": driver_state.tyre_compound.value,
                    "tyre_age": driver_state.tyre_age,
                    "fuel_kg": driver_state.fuel_mass,
                    "gap_ahead": driver_state.gap_ahead,
                },
                strategy=strategy,
                competitors=competitors,
                track_pit_lane_loss=track.pit_stop_time_loss,
                laps_remaining=config.total_laps - lap,
                safety_car_active=race_state.safety_car_deployed,
                safety_car_probability=0.15,
                weather_change_imminent=forecast_rain,
            )
            if decision.should_pit_now:
                driver_state.is_in_pits = True
                pit_loss = track.pit_stop_time_loss + rng.normal(0, 0.5)
                driver_state.total_time += pit_loss
                driver_state.tyre_wear = 0.0
                driver_state.tyre_age = 0
                driver_state.tyre_temp = 90.0
                try:
                    driver_state.tyre_compound = TyreCompound(decision.recommended_compound)
                except ValueError:
                    pass  # keep current compound on unplanned/empty recommendation
                driver_state.is_in_pits = False

    def _handle_safety_car_restart(
        self,
        driver_states: dict[str, DriverState],
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        lap: int,
        config: SimulationConfig,
        race_state: RaceState,
        weather_state,
        rng: RandomProvider,
        events: list[dict],
    ) -> None:
        """Handle safety car restart dynamics (compression + reactions)."""
        driver_data = []
        for driver_id, state in driver_states.items():
            if state.status != DriverStatus.ACTIVE:
                continue
            driver = next(d for d in drivers if d.id == driver_id)
            driver_data.append({
                "driver_id": driver_id,
                "position": state.position,
                "gap_ahead": state.gap_ahead,
                "tyre_compound": state.tyre_compound.value,
                "tyre_age": state.tyre_age,
                "tyre_temp": state.tyre_temp,
                "start_performance": driver.start_performance,
                "pressure_resistance": driver.pressure_resistance,
                "aggression": driver.aggression,
                "consistency": driver.consistency,
            })
        compressed = self.safety_car_restart_model.compress_field(
            driver_data, rng.get_stream("restart")
        )
        for cd in compressed:
            driver_states[cd["driver_id"]].gap_ahead = cd["gap_ahead"]
        gaps_before = [d["gap_ahead"] for d in driver_data]
        gaps_after = [cd["gap_ahead"] for cd in compressed]
        for cd in compressed:
            driver_id = cd["driver_id"]
            state = driver_states[driver_id]
            driver = next(d for d in drivers if d.id == driver_id)
            w_str = race_state.weather_condition.value if hasattr(
                race_state.weather_condition, "value") else str(race_state.weather_condition)
            restart_context = SafetyCarRestartContext(
                driver_id=driver_id,
                position=state.position,
                gap_to_ahead=state.gap_ahead,
                tyre_compound=state.tyre_compound.value,
                tyre_age=state.tyre_age,
                tyre_temp=state.tyre_temp,
                start_performance=driver.start_performance,
                pressure_resistance=driver.pressure_resistance,
                aggression=driver.aggression,
                consistency=driver.consistency,
                weather=w_str,
                track_wetness=race_state.track_wetness,
                track_temp=weather_state.track_temperature if hasattr(
                    weather_state, "track_temperature") else 35.0,
                laps_under_sc=race_state.safety_car_laps_remaining if hasattr(
                    race_state, "safety_car_laps_remaining") else 3,
                is_leader=(state.position == 1),
            )
            restart_result = self.safety_car_restart_model.evaluate_restart(
                restart_context, rng.get_stream("restart")
            )
            state.total_time += restart_result.reaction_time * 0.1
        active = [ds for ds in driver_states.values() if ds.status == DriverStatus.ACTIVE]
        ts = sum(ds.total_time for ds in active) / max(1, len(active))
        restart_event = create_safety_car_restarted_event(
            timestamp=ts,
            lap=lap,
            leader_id=next(d["driver_id"] for d in compressed if d["position"] == 1),
            field_compressed=True,
            gaps_before=gaps_before,
            gaps_after=gaps_after,
        )
        events.append(restart_event.model_dump())

    def _build_resource_state(self, driver_state: DriverState) -> BattleResourceState:
        """Build fuel/ERS/tyre resource state (prevents unlimited attack)."""
        fuel_target = float(getattr(driver_state, "fuel_target", 5.0))
        return BattleResourceState(
            fuel_mass=driver_state.fuel_mass,
            fuel_target=fuel_target,
            fuel_mode=str(getattr(driver_state, "fuel_mode", "standard")),
            ers_energy=driver_state.ers_charge,
            ers_mode=str(driver_state.ers_mode),
            ers_target=0.5,
            tyre_condition=1.0 - driver_state.tyre_wear,
            tyre_wear=driver_state.tyre_wear,
            tyre_compound=driver_state.tyre_compound.value,
            tyre_age=driver_state.tyre_age,
            fuel_delta_to_target=driver_state.fuel_mass - fuel_target,
            ers_delta_to_target=driver_state.ers_charge - 0.5,
            can_attack=(driver_state.fuel_mass > fuel_target + 1.0 and driver_state.ers_charge > 0.2),  # noqa: E501
            fuel_conservation_required=driver_state.fuel_mass < fuel_target + 2.0,
            ers_conservation_required=driver_state.ers_charge < 0.3,
        )

    def _apply_resource_costs(
        self,
        driver_state: DriverState,
        attacking: bool,
        defending: bool,
        config: SimulationConfig,
        events: list[dict],
        lap: int,
        timestamp: float,
    ) -> None:
        """Apply fuel/ERS costs for battle actions + emit mode-change events."""
        if attacking:
            driver_state.fuel_mass = max(0.0, driver_state.fuel_mass - config.fuel_attack_cost * 0.2)  # noqa: E501
            driver_state.ers_charge = max(0.0, driver_state.ers_charge - config.ers_attack_cost * 0.4)  # noqa: E501
            if driver_state.ers_mode != "overtake":
                events.append(create_ers_mode_changed_event(
                    timestamp=timestamp, lap=lap, driver_id=driver_state.driver_id,
                    old_mode=driver_state.ers_mode, new_mode="overtake", reason="attack",
                ).model_dump())
                driver_state.ers_mode = "overtake"
        elif defending:
            driver_state.fuel_mass = max(0.0, driver_state.fuel_mass - config.defense_fuel_cost * 0.2)  # noqa: E501
            driver_state.ers_charge = max(0.0, driver_state.ers_charge - config.ers_attack_cost * 0.15)  # noqa: E501
        else:
            driver_state.ers_charge = min(1.0, driver_state.ers_charge + config.ers_harvest_rate * 0.3)  # noqa: E501

    def _process_racing_dynamics(
        self,
        driver_states: dict[str, DriverState],
        drivers: list[Driver],
        cars: dict[str, Car],
        track: Track,
        lap: int,
        config: SimulationConfig,
        race_state: RaceState,
        weather_state,
        rng: RandomProvider,
        events: list[dict],
        sampler: TelemetrySampler | None = None,
    ) -> None:
        """Process battles, DRS trains, defense, wetness, crossover, team orders."""
        if race_state.safety_car_deployed or race_state.vsc_active:
            return
        active_now = [ds for ds in driver_states.values() if ds.status == DriverStatus.ACTIVE]
        # Phase 8 perf: single timestamp + single tyre-spec lookup + driver map per lap
        timestamp = sum(ds.total_time for ds in active_now) / max(1, len(active_now))
        tyre_specs = get_standard_tyre_specs()
        driver_map = {d.id: d for d in drivers}
        weather_str = race_state.weather_condition.value if hasattr(
            race_state.weather_condition, "value") else str(race_state.weather_condition)

        prev_intensity = float(getattr(race_state, "rain_intensity", 0.0))
        new_intensity = min(1.0, float(getattr(weather_state, "precipitation_rate", 0.0)) / 10.0)
        if abs(new_intensity - prev_intensity) > 0.05:
            events.append(create_rain_intensity_changed_event(
                timestamp=timestamp, lap=lap, old_intensity=prev_intensity,
                new_intensity=new_intensity,
                precipitation_rate=float(getattr(weather_state, "precipitation_rate", 0.0)),
            ).model_dump())
            race_state.rain_intensity = new_intensity
        if self.track_wetness_model is not None:
            try:
                self.track_wetness_model._rng = rng.get_stream("drying_line")
            except Exception:
                pass
            wetness_map = self.track_wetness_model.step(weather_state, len(active_now))
            rl = float(sum(s.racing_line_wetness for s in wetness_map.values()) / max(1, len(wetness_map)))  # noqa: E501
            ol = float(sum(s.off_line_wetness for s in wetness_map.values()) / max(1, len(wetness_map)))  # noqa: E501
            if abs(rl - race_state.racing_line_wetness) > 0.02 or abs(ol - race_state.off_line_wetness) > 0.02:  # noqa: E501
                events.append(create_track_wetness_changed_event(
                    timestamp=timestamp, lap=lap, sector=-1,
                    old_wetness=float(race_state.track_wetness), new_wetness=float((rl + ol) / 2),
                    racing_line_wetness=rl, off_line_wetness=ol,
                ).model_dump())
                for sector, s in wetness_map.items():
                    events.append(create_drying_line_event(
                        timestamp=timestamp, lap=lap, sector=int(sector),
                        racing_line_wetness=float(s.racing_line_wetness),
                        off_line_wetness=float(s.off_line_wetness),
                        drying_rate=float(s.off_line_wetness - s.racing_line_wetness),
                    ).model_dump())
                    break
            race_state.racing_line_wetness = rl
            race_state.off_line_wetness = ol
            race_state.track_wetness = (rl + ol) / 2
            race_state.precipitation_rate = float(getattr(weather_state, "precipitation_rate", 0.0))

        sorted_drivers = sorted(active_now, key=lambda x: x.position)
        position_list = [
            {"driver_id": ds.driver_id, "position": ds.position, "gap_ahead": ds.gap_ahead}
            for ds in sorted_drivers
        ]
        drs_train_context = DRSTrainContext(
            positions=position_list, track_drs_zones=track.drs_zones, drs_detection_gap=1.0,
        )
        drs_train_info = self.drs_train_model.detect_train(drs_train_context)
        if drs_train_info.train_detected:
            events.append(create_drs_train_formed_event(
                timestamp=timestamp, lap=lap, leader_id=drs_train_info.leader_id,
                members=drs_train_info.members, train_length=drs_train_info.train_length,
                gaps=drs_train_info.gaps,
            ).model_dump())

        for i in range(len(sorted_drivers) - 1):
            attacker_state = sorted_drivers[i + 1]
            defender_state = sorted_drivers[i]
            attacker_driver = driver_map[attacker_state.driver_id]
            defender_driver = driver_map[defender_state.driver_id]
            attacker_car = cars[attacker_state.driver_id]
            gap = attacker_state.gap_ahead
            if gap > config.battle_candidate_gap:
                continue
            attacker_pace = attacker_state.last_lap_time or 90.0
            defender_pace = defender_state.last_lap_time or 90.0
            relative_pace = attacker_pace - defender_pace
            attacker_tyre_spec = tyre_specs[attacker_state.tyre_compound]
            defender_tyre_spec = tyre_specs[defender_state.tyre_compound]
            tyre_delta = 0.0
            if attacker_tyre_spec.base_pace_factor < defender_tyre_spec.base_pace_factor:
                tyre_delta = (defender_tyre_spec.base_pace_factor - attacker_tyre_spec.base_pace_factor) * 1.5  # noqa: E501
            elif attacker_tyre_spec.base_pace_factor > defender_tyre_spec.base_pace_factor:
                tyre_delta = -(attacker_tyre_spec.base_pace_factor - defender_tyre_spec.base_pace_factor) * 1.5  # noqa: E501
            tyre_delta += (defender_state.tyre_age - attacker_state.tyre_age) * 0.02

            sector = 0
            try:
                dirty_air_context = DirtyAirContext(
                    following_distance=gap, corner_type="medium",
                    follower_aero_sensitivity=getattr(attacker_car, "aero_sensitivity", 50),
                    leader_aero_efficiency=getattr(cars[defender_state.driver_id], "aero_efficiency", 50),  # noqa: E501
                    weather=weather_str, track_wetness=race_state.track_wetness, speed_kmh=250.0,
                )
                dirty_air_effect = self.dirty_air_model.calculate_effect_for_sector(
                    dirty_air_context, sector, track
                )
            except Exception:
                dirty_air_context = DirtyAirContext(
                    following_distance=gap, corner_type="medium",
                    follower_aero_sensitivity=50, leader_aero_efficiency=50,
                    weather=weather_str, track_wetness=race_state.track_wetness, speed_kmh=250.0,
                )
                dirty_air_effect = self.dirty_air_model.calculate_effect(dirty_air_context)

            drs_available = bool(attacker_state.drs_active)
            if drs_train_info.train_detected:
                drs_available = drs_available and bool(drs_train_info.effective_overtake_opportunity)  # noqa: E501
            overtake_zone = None
            if self.overtake_map is not None:
                try:
                    overtake_zone = self.overtake_map.get_zone_for_sector(sector)
                except Exception:
                    overtake_zone = None

            attacker_resource = self._build_resource_state(attacker_state)
            defender_resource = self._build_resource_state(defender_state)
            off_line_gap = float(race_state.off_line_wetness - race_state.racing_line_wetness)
            off_line_penalty_active = bool(off_line_gap > 0.15)

            overtake_context = OvertakeContext(
                attacker_id=attacker_state.driver_id, defender_id=defender_state.driver_id,
                attacker_position=attacker_state.position, defender_position=defender_state.position,  # noqa: E501
                gap=gap, relative_pace=relative_pace,
                attacker_tyre_compound=attacker_state.tyre_compound.value,
                defender_tyre_compound=defender_state.tyre_compound.value,
                attacker_tyre_age=attacker_state.tyre_age, defender_tyre_age=defender_state.tyre_age,  # noqa: E501
                tyre_delta=tyre_delta, attacker_ers_mode=attacker_state.ers_mode,
                defender_ers_mode=defender_state.ers_mode, drs_available=drs_available,
                attacker_straight_line_advantage=0.0,
                defender_defensive_skill=defender_driver.defending,
                attacker_overtaking_skill=attacker_driver.overtaking,
                attacker_aggression=attacker_driver.aggression,
                track_overtaking_difficulty=track.get_sector_overtaking_difficulty(sector) / 100.0,
                corner_type="medium", dirty_air_effect=dirty_air_effect.total_pace_loss,
                weather=weather_str, track_wetness=race_state.track_wetness,
                attacker_damage=attacker_state.aero_damage + attacker_state.engine_damage,
                defender_damage=defender_state.aero_damage + defender_state.engine_damage,
                safety_car_active=race_state.safety_car_deployed, vsc_active=race_state.vsc_active,
                traffic_ahead=False,
                attacker_resource_state=attacker_resource, defender_resource_state=defender_resource,  # noqa: E501
                overtake_zone=overtake_zone, sector=sector, forecast=self.forecast_model,
                track_wetness_racing_line=race_state.racing_line_wetness,
                track_wetness_off_line=race_state.off_line_wetness,
                drying_line_active=off_line_penalty_active,
                attacker_ers_energy=attacker_state.ers_charge, defender_ers_energy=defender_state.ers_charge,  # noqa: E501
            )
            overtake_decision = self.overtake_engine.evaluate_opportunity(
                overtake_context, rng.get_stream("overtaking")
            )
            if overtake_decision.opportunity_exists and overtake_decision.probability > 0.15:
                events.append(create_overtake_opportunity_event(
                    timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                    defender_id=defender_state.driver_id, probability=overtake_decision.probability,
                    sector=sector, drs_available=drs_available,
                ).model_dump())

            battle_context = BattleContext(
                attacker_id=attacker_state.driver_id, defender_id=defender_state.driver_id,
                gap=gap, relative_pace=relative_pace, tyre_delta=tyre_delta, drs_state=drs_available,  # noqa: E501
                attacker_ers_mode=attacker_state.ers_mode, defender_ers_mode=defender_state.ers_mode,  # noqa: E501
                track_overtaking_difficulty=track.get_sector_overtaking_difficulty(sector) / 100.0,
                dirty_air=dirty_air_effect.total_pace_loss,
                attacker_overtaking_skill=attacker_driver.overtaking,
                defender_defensive_skill=defender_driver.defending,
                attacker_aggression=attacker_driver.aggression,
                defender_aggression=defender_driver.aggression,
                attacker_tyre_condition=1.0 - attacker_state.tyre_wear,
                defender_tyre_condition=1.0 - defender_state.tyre_wear,
                weather=weather_str, track_wetness=race_state.track_wetness,
                attacker_damage=attacker_state.aero_damage + attacker_state.engine_damage,
                defender_damage=defender_state.aero_damage + defender_state.engine_damage,
                safety_car_active=race_state.safety_car_deployed, vsc_active=race_state.vsc_active,
                current_lap=lap, race_laps_remaining=config.total_laps - lap,
                attacker_resource_state=attacker_resource, defender_resource_state=defender_resource,  # noqa: E501
                overtake_zone=overtake_zone, sector=sector, forecast=self.forecast_model,
                track_wetness_racing_line=race_state.racing_line_wetness,
                track_wetness_off_line=race_state.off_line_wetness,
                drying_line_active=off_line_penalty_active,
            )
            battle_decision = self.battle_engine.update_battle(battle_context, rng.get_stream("battle"))  # noqa: E501
            battle = self.battle_engine.get_battle(attacker_state.driver_id, defender_state.driver_id)  # noqa: E501
            if battle and battle.laps_active == 1:
                events.append(create_battle_started_event(
                    timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                    defender_id=defender_state.driver_id, gap=gap, drs_available=drs_available,
                ).model_dump())
            elif battle and battle.state != battle_decision.new_state:
                if battle_decision.new_state == BattleStateType.SIDE_BY_SIDE:
                    events.append(create_battle_side_by_side_event(
                        timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                        defender_id=defender_state.driver_id, gap=gap,
                    ).model_dump())
                elif battle_decision.new_state == BattleStateType.BATTLE_ENDED:
                    events.append(create_battle_ended_event(
                        timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                        defender_id=defender_state.driver_id, reason="gap_increased",
                        duration_laps=battle.laps_active,
                    ).model_dump())
                self._emit(events, config, create_battle_updated_event(
                    timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                    defender_id=defender_state.driver_id, state=battle_decision.new_state.value,
                    gap=gap, overtake_probability=battle_decision.overtake_probability,
                ).model_dump(), "standard")

            is_teammate = attacker_driver.team_id == defender_driver.team_id
            team_order = None
            if is_teammate and self.team_order_model is not None:
                from app.simulation.strategy.team_orders import TeamOrderContext as _TOC

                toc = _TOC(
                    team_id=attacker_driver.team_id, driver_id=attacker_state.driver_id,
                    teammate_id=defender_state.driver_id, position=attacker_state.position,
                    teammate_position=defender_state.position, gap=gap, pace_difference=relative_pace,  # noqa: E501
                    tyre_condition=1.0 - attacker_state.tyre_wear,
                    teammate_tyre_condition=1.0 - defender_state.tyre_wear,
                    laps_remaining=config.total_laps - lap,
                )
                t_dec = self.team_order_model.evaluate(toc, rng.get_stream("team_orders"))
                team_order = t_dec.order
                if team_order:
                    events.append(create_team_order_issued_event(
                        timestamp=timestamp, lap=lap, team_id=attacker_driver.team_id,
                        driver_id=attacker_state.driver_id, order=team_order,
                        target_driver_id=defender_state.driver_id, reason=t_dec.reason,
                    ).model_dump())
                    events.append(create_team_order_executed_event(
                        timestamp=timestamp, lap=lap, team_id=attacker_driver.team_id,
                        driver_id=attacker_state.driver_id, order=team_order, complied=True,
                    ).model_dump())

            defense_context = DefenseContext(
                defender_id=defender_state.driver_id, attacker_id=attacker_state.driver_id,
                gap=gap, relative_pace=relative_pace,
                defender_defensive_skill=defender_driver.defending,
                defender_aggression=defender_driver.aggression,
                defender_pressure_resistance=defender_driver.pressure_resistance,
                defender_tyre_condition=1.0 - defender_state.tyre_wear,
                attacker_overtaking_skill=attacker_driver.overtaking,
                attacker_aggression=attacker_driver.aggression,
                attacker_tyre_condition=1.0 - attacker_state.tyre_wear,
                track_overtaking_difficulty=track.get_sector_overtaking_difficulty(sector) / 100.0,
                corner_type="medium", weather=weather_str, track_wetness=race_state.track_wetness,
                laps_remaining=config.total_laps - lap, position=defender_state.position,
                defender_resource_state=defender_resource, attacker_resource_state=attacker_resource,  # noqa: E501
                overtake_zone=overtake_zone, sector=sector, forecast=self.forecast_model,
                track_wetness_racing_line=race_state.racing_line_wetness,
                track_wetness_off_line=race_state.off_line_wetness,
                drying_line_active=off_line_penalty_active,
                is_teammate=is_teammate, team_order=team_order,
            )
            defense_decision = self.defense_model.evaluate_defense(
                defense_context, rng.get_stream("defense")
            )
            self._emit(events, config, create_defense_action_event(
                timestamp=timestamp, lap=lap, defender_id=defender_state.driver_id,
                attacker_id=attacker_state.driver_id, mode=defense_decision.mode.value,
                line_choice=defense_decision.line_choice, pace_cost=defense_decision.pace_cost,
                incident_risk_multiplier=defense_decision.incident_risk_multiplier,
            ).model_dump(), "standard")

            # Phase 8: multi-lap battle resource planning (bounded heuristic)
            if self.battle_planner is not None and battle_decision.new_state.value in (
                "attacking", "side_by_side", "within_drs",
            ):
                plan = self.battle_planner.plan(
                    attacker_resource, defender_resource, gap, tyre_delta,
                    config.total_laps - lap, rng.get_stream("planner"),
                )
                if plan.action_now == "harvest" and attacker_state.ers_mode != "low":
                    old_mode = attacker_state.ers_mode
                    attacker_state.ers_mode = "low"
                    self._emit(events, config, create_ers_mode_changed_event(
                        timestamp=timestamp, lap=lap, driver_id=attacker_state.driver_id,
                        old_mode=old_mode, new_mode="low", reason="battle_plan_harvest",
                    ).model_dump(), "standard")

            attacking = bool(overtake_decision.opportunity_exists and overtake_decision.recommended_action == "attack")  # noqa: E501
            defending = bool(defense_decision.mode.value in ("defensive", "aggressive"))
            self._apply_resource_costs(attacker_state, attacking, False, config, events, lap, timestamp)  # noqa: E501
            self._apply_resource_costs(defender_state, False, defending, config, events, lap, timestamp)  # noqa: E501

            if attacking:
                events.append(create_overtake_attempted_event(
                    timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                    defender_id=defender_state.driver_id, success_probability=overtake_decision.probability,  # noqa: E501
                ).model_dump())
                success, reason = self.overtake_engine.evaluate_attempt(
                    overtake_context, rng.get_stream("overtaking")
                )
                if success:
                    events.append(create_overtake_completed_event(
                        timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                        defender_id=defender_state.driver_id, was_successful=True,
                        gap_before=gap, gap_after=gap * 0.5,
                    ).model_dump())
                    self.battle_engine.record_attack_attempt(
                        attacker_state.driver_id, defender_state.driver_id, True
                    )
                else:
                    events.append(create_overtake_failed_event(
                        timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                        defender_id=defender_state.driver_id, reason=reason, gap_before=gap,
                    ).model_dump())
                    self.battle_engine.record_attack_attempt(
                        attacker_state.driver_id, defender_state.driver_id, False
                    )
                    if reason == "incident":
                        self.battle_engine.record_incident(
                            attacker_state.driver_id, defender_state.driver_id
                        )

            # Phase 8: per-sector refinement (gated: only for battles in an
            # active state, so backmarkers cruising in CLOSING pay no extra
            # model cost; events only at FULL_TELEMETRY via "sector" stream)
            _active_states = ("attacking", "side_by_side", "within_drs", "defending")
            if (
                battle is not None
                and battle_decision.new_state.value in _active_states
                and len(attacker_state.sector_times) == len(defender_state.sector_times)
                and attacker_state.sector_times
            ):
                from app.simulation.racing.sectors import sector_gap_trace

                n_sec = len(attacker_state.sector_times)
                sec_gaps = sector_gap_trace(
                    defender_state.sector_times, attacker_state.sector_times, gap
                )
                wet_map = (self.track_wetness_model.sector_wetness
                           if self.track_wetness_model is not None else {})
                for s_idx in range(n_sec):
                    s_gap = sec_gaps[s_idx]
                    if s_gap > config.battle_candidate_gap:
                        continue
                    corner_counts = track.get_sector_corner_counts(s_idx)
                    s_corner = "medium"
                    if corner_counts:
                        top = max(corner_counts, key=lambda k: corner_counts[k])
                        s_corner = top.value if hasattr(top, "value") else str(top)
                    s_wet = wet_map.get(s_idx)
                    s_rl = float(s_wet.racing_line_wetness) if s_wet else race_state.racing_line_wetness  # noqa: E501
                    s_ol = float(s_wet.off_line_wetness) if s_wet else race_state.off_line_wetness
                    try:
                        s_da_ctx = DirtyAirContext(
                            following_distance=max(0.1, s_gap), corner_type=s_corner,
                            follower_aero_sensitivity=getattr(attacker_car, "aero_sensitivity", 50),
                            leader_aero_efficiency=getattr(
                                cars[defender_state.driver_id], "aero_efficiency", 50),
                            weather=weather_str, track_wetness=(s_rl + s_ol) / 2,
                            speed_kmh=250.0,
                        )
                        s_da = self.dirty_air_model.calculate_effect_for_sector(
                            s_da_ctx, s_idx, track
                        )
                    except Exception:
                        s_da = dirty_air_effect
                    self._emit(events, config, create_sector_completed_event(
                        timestamp=timestamp, lap=lap, driver_id=attacker_state.driver_id,
                        sector=s_idx, sector_time=attacker_state.sector_times[s_idx],
                        gap_after_sector=s_gap,
                    ).model_dump(), "full")
                    # Phase 8 perf: sector probability is the lap-level decision
                    # scaled by sector opportunity (pure arithmetic, no extra
                    # engine evaluation or RNG draw per sector).
                    s_opp = track.get_sector_overtaking_opportunity(s_idx)
                    s_scale = (s_opp / 50.0) if s_opp > 0 else 1.0
                    if drs_available and track.get_sector_drs_zones(s_idx) == 0:
                        s_scale *= 0.7
                    s_probability = min(
                        0.9, overtake_decision.probability * s_scale
                        + (0.05 if s_ol - s_rl < 0.1 else -0.05)
                        - max(0.0, s_da.total_pace_loss - dirty_air_effect.total_pace_loss) * 0.5)
                    if overtake_decision.opportunity_exists and s_probability > 0.3:
                        self._emit(events, config, create_sector_overtake_opportunity_event(
                            timestamp=timestamp, lap=lap, attacker_id=attacker_state.driver_id,
                            defender_id=defender_state.driver_id, sector=s_idx,
                            probability=s_probability,
                        ).model_dump(), "full")

        if self.tyre_crossover_model is not None and self.track_wetness_model is not None:
            wet_map = self.track_wetness_model.sector_wetness
            s0 = wet_map.get(0) if wet_map else None
            if s0 is not None:
                for driver_id, state in driver_states.items():
                    if state.status != DriverStatus.ACTIVE:
                        continue
                    assessment = self.tyre_crossover_model.assess_crossover(
                        current_compound=state.tyre_compound.value,
                        track_wetness=(float(s0.racing_line_wetness) + float(s0.off_line_wetness)) / 2,  # noqa: E501
                        track_temp=35.0,
                        racing_line_wetness=float(s0.racing_line_wetness),
                        off_line_wetness=float(s0.off_line_wetness),
                        tyre_temp=state.tyre_temp, tyre_wear=state.tyre_wear,
                        forecast_wetness=None,
                    )
                    if assessment.recommended_compound != state.tyre_compound.value and assessment.confidence > 0.7:  # noqa: E501
                        events.append(create_tyre_crossover_event(
                            timestamp=timestamp, lap=lap, driver_id=driver_id,
                            old_compound=state.tyre_compound.value,
                            new_compound=assessment.recommended_compound,
                            reason=assessment.reason, confidence=assessment.confidence,
                            expected_delta=assessment.expected_delta,
                        ).model_dump())

    def _compile_results(
        self,
        config: SimulationConfig,
        drivers: list[Driver],
        cars: dict[str, Car],
        driver_states: dict[str, DriverState],
        track: Track,
        total_laps: int,
        events: list,
        rng: RandomProvider,
        telemetry: list[dict] | None = None,
    ) -> RaceResult:
        """Compile final race results."""
        results = []
        for driver_id, ds in driver_states.items():
            driver = next(d for d in drivers if d.id == driver_id)
            car = cars.get(driver_id)
            if ds.status == DriverStatus.RETIRED:
                position = ds.position
                total_time = None
            else:
                position = ds.position
                total_time = ds.total_time
            results.append(DriverResult(
                driver_id=driver_id,
                position=position,
                total_time=total_time,
                laps_completed=ds.lap,
                best_lap_time=ds.best_lap_time,
                best_lap_number=ds.lap if ds.best_lap_time else None,
                status=ds.status,
                dnf_reason=ds.dnf_reason,
                pit_stops=0,
                points=0.0,
            ))
        results.sort(key=lambda x: x.position)
        points_system = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        for i, result in enumerate(results):
            if i < len(points_system) and result.status != DriverStatus.RETIRED:
                result.points = points_system[i]
        fastest = min(
            [(r.driver_id, r.best_lap_time) for r in results if r.best_lap_time],
            key=lambda x: x[1],
            default=(None, None)
        )
        return RaceResult(
            simulation_id=config.simulation_id if hasattr(config, 'simulation_id') else "race_001",
            seed=rng.seed,
            model_version=config.model_version,
            track_id=track.id,
            session_type=SessionType.RACE,
            total_laps=total_laps,
            completed_laps=total_laps,
            results=results,
            events=events,
            fastest_lap={"driver_id": fastest[0], "time": fastest[1], "lap": total_laps} if fastest[0] else None,  # noqa: E501
            weather_history=[],
            safety_car_periods=[],
            start_time="",
            end_time="",
            duration_seconds=0.0,
            telemetry=telemetry or [],
            reproducibility={
                "seed": rng.seed,
                "simulation_version": SIMULATION_VERSION,
                "model_version": MODEL_VERSION,
                "config_version": CONFIG_VERSION,
                "track_id": track.id,
                "drivers": [d.id for d in drivers],
                "teams": sorted({d.team_id for d in drivers}),
                "streams": ["forecast", "drying_line", "overtaking", "battle",
                            "defense", "restart", "team_orders", "formation",
                            "start", "sector", "red_flag", "sprint", "planner", "race_control"],
                "race_control_model_version": "racecontrol-v1.0.0",
                "race_control_policy_version": "racecontrol-policy-v1.0.0",
                "race_control_enabled": config.race_control_enabled,
                "race_control_history": getattr(self, "race_control_history", [])[:20],
            },
            simulation_version=SIMULATION_VERSION,
            config_version=CONFIG_VERSION,
        )

