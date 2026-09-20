"""Phase 20 — Car Setup & Vehicle Configuration Engine tests."""
import pytest

from app.simulation.setup.models import (
    SetupState,
    SetupParameters,
    SetupConstraints,
    SetupEffects,
    SetupEvidence,
    EvidenceTier,
    ConstraintType,
    SetupMode,
    ParameterEvidence,
    create_baseline_setup,
    create_setup_from_dict,
    get_era_constraints,
)
from app.simulation.setup.engine import SetupEngine, get_default_coefficients, get_track_modifiers
from app.simulation.setup.validator import SetupValidator
from app.simulation.setup.fingerprint import setup_fingerprint, verify_fingerprint
from app.simulation.setup.integration import SetupAwareLapTimeModel, compute_setup_lap_time_delta
from app.simulation.models.car import Car
from app.simulation.models.track import Track, get_2024_calendar


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def test_setup_parameter_creation():
    """Test SetupParameter creation with evidence."""
    from app.simulation.setup.models import SetupParameter
    param = SetupParameter(
        name="front_wing",
        value=5.0,
        minimum=1.0,
        maximum=10.0,
        step=0.5,
        unit="degrees",
        evidence=ParameterEvidence(tier=EvidenceTier.PRIOR_ONLY, source="prior"),
        constraint_type=ConstraintType.MODEL_PHYSICAL,
    )
    assert param.name == "front_wing"
    assert param.value == 5.0
    assert param.is_valid()
    assert param.get_evidence_tier() == EvidenceTier.PRIOR_ONLY


def test_setup_parameters_defaults():
    """Test SetupParameters has all required parameters with defaults."""
    params = SetupParameters()
    expected_params = [
        "front_wing", "rear_wing",
        "ride_height_front", "ride_height_rear",
        "front_anti_roll", "rear_anti_roll",
        "front_spring", "rear_spring",
        "brake_bias",
        "diff_entry", "diff_mid", "diff_exit",
        "front_camber", "rear_camber",
        "front_toe", "rear_toe",
        "tyre_pressure_front", "tyre_pressure_rear",
    ]
    for name in expected_params:
        assert hasattr(params, name)
        param = getattr(params, name)
        assert param.name == name
        assert param.minimum <= param.value <= param.maximum


def test_setup_evidence_tiers():
    """Test that evidence tiers are correctly assigned."""
    params = SetupParameters()
    evidence_map = params.get_evidence_map()

    # Aero params should be PRIOR_ONLY
    assert evidence_map["front_wing"] == EvidenceTier.PRIOR_ONLY
    assert evidence_map["rear_wing"] == EvidenceTier.PRIOR_ONLY

    # Tyre pressure should be NON_IDENTIFIABLE
    assert evidence_map["tyre_pressure_front"] == EvidenceTier.NON_IDENTIFIABLE
    assert evidence_map["tyre_pressure_rear"] == EvidenceTier.NON_IDENTIFIABLE


def test_setup_state_creation():
    """Test SetupState creation with all fields."""
    setup = create_baseline_setup(
        car_id="RB20",
        constructor_id="RED_BULL",
        season="2024",
        track_id="monaco",
    )
    assert setup.setup_id == "baseline_RB20_monaco"
    assert setup.car_id == "RB20"
    assert setup.constructor_id == "RED_BULL"
    assert setup.season == "2024"
    assert setup.track_id == "monaco"
    assert setup.mode == SetupMode.HYPOTHETICAL
    assert setup.fingerprint is not None
    assert len(setup.fingerprint) == 16  # SHA256 truncated to 16 chars


def test_setup_state_serialization():
    """Test SetupState serializes and deserializes correctly."""
    setup = create_baseline_setup(car_id="TEST", track_id="monaco")
    data = setup.model_dump()
    assert data["car_id"] == "TEST"
    assert data["track_id"] == "monaco"
    assert "parameters" in data
    assert "evidence" in data
    assert "provenance" in data


def test_setup_fingerprint_deterministic():
    """Test setup fingerprint is deterministic."""
    setup1 = create_baseline_setup(car_id="TEST", track_id="monaco")
    setup2 = create_baseline_setup(car_id="TEST", track_id="monaco")
    assert setup1.fingerprint == setup2.fingerprint


def test_setup_fingerprint_changes_with_params():
    """Test fingerprint changes when parameters change."""
    setup1 = create_baseline_setup(car_id="TEST", track_id="monaco")
    setup2 = create_setup_from_dict(
        {"front_wing": 8.0, "rear_wing": 8.0},
        car_id="TEST",
        track_id="monaco",
    )
    assert setup1.fingerprint != setup2.fingerprint


def test_verify_fingerprint():
    """Test fingerprint verification."""
    setup = create_baseline_setup(car_id="TEST", track_id="monaco")
    assert verify_fingerprint(setup, setup.fingerprint)
    assert not verify_fingerprint(setup, "invalid_fingerprint")


def test_create_setup_from_dict():
    """Test creating setup from parameter dict."""
    custom_params = {"front_wing": 8.0, "rear_wing": 3.0, "brake_bias": 58.0}
    setup = create_setup_from_dict(
        custom_params,
        car_id="TEST",
        track_id="monza",
    )
    assert setup.parameters.front_wing.value == 8.0
    assert setup.parameters.rear_wing.value == 3.0
    assert setup.parameters.brake_bias.value == 58.0


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validator_passes_valid_setup():
    """Test validator passes valid baseline setup."""
    setup = create_baseline_setup(car_id="TEST", track_id="monaco")
    validator = SetupValidator(era="2022-2026", track_id="monaco")
    result = validator.validate(setup)
    assert result.is_valid
    assert len(result.violations) == 0


def test_validator_catches_out_of_bounds():
    """Test validator catches out-of-bounds values."""
    setup = create_setup_from_dict(
        {"front_wing": 15.0, "rear_wing": -1.0},  # Both invalid
        car_id="TEST",
        track_id="monaco",
    )
    validator = SetupValidator(era="2022-2026")
    result = validator.validate(setup)
    assert not result.is_valid
    assert len(result.violations) >= 2


def test_validator_warnings():
    """Test validator produces warnings for questionable setups."""
    # Extreme rake
    setup = create_setup_from_dict(
        {"ride_height_front": 40.0, "ride_height_rear": 15.0},  # Negative rake
        car_id="TEST",
        track_id="monaco",
    )
    validator = SetupValidator(era="2022-2026", track_id="monaco")
    result = validator.validate(setup)
    # Should have warning about negative rake
    assert any("rake" in w.lower() for w in result.warnings)


def test_validator_track_specific_warnings():
    """Test track-specific warnings."""
    # Low wing at Monaco should warn
    setup = create_setup_from_dict(
        {"front_wing": 2.0, "rear_wing": 2.0},
        car_id="TEST",
        track_id="monaco",
    )
    validator = SetupValidator(era="2022-2026", track_id="monaco")
    result = validator.validate(setup)
    assert any("monaco" in w.lower() for w in result.warnings)


def test_validator_clamp():
    """Test validate_and_clamp returns valid setup."""
    setup = create_setup_from_dict(
        {"front_wing": 15.0, "rear_wing": -1.0},
        car_id="TEST",
        track_id="monaco",
    )
    validator = SetupValidator(era="2022-2026")
    clamped, result = validator.validate_and_clamp(setup)
    # Original validation must report violations
    assert not result.is_valid
    assert len(result.violations) >= 2
    # Clamped copy must be within bounds and validate clean
    assert clamped.parameters.front_wing.value == 10.0  # Clamped to max
    assert clamped.parameters.rear_wing.value == 1.0  # Clamped to min
    result2 = validator.validate(clamped)
    assert result2.is_valid


def test_validator_era_constraints():
    """Test era-specific constraints."""
    # Modern era has higher minimum ride height
    modern_constraints = get_era_constraints("2022-2026")
    older_constraints = get_era_constraints("2014-2021")

    assert modern_constraints.parameters["ride_height_front"]["minimum"] >= \
        older_constraints.parameters["ride_height_front"]["minimum"]


# ---------------------------------------------------------------------------
# Engine - Coefficients
# ---------------------------------------------------------------------------

def test_default_coefficients_exist():
    """Test default coefficients are defined for all parameters."""
    coeffs = get_default_coefficients()

    # Check aero
    assert "front_wing" in coeffs.downforce
    assert "rear_wing" in coeffs.downforce
    assert coeffs.downforce["front_wing"] > 0
    assert coeffs.drag["rear_wing"] > 0

    # Check mechanical
    assert "front_anti_roll" in coeffs.cornering_stiffness
    assert "brake_bias" in coeffs.braking_stability

    # Check tyre
    assert "front_camber" in coeffs.front_tyre_deg
    assert "tyre_pressure_front" in coeffs.front_tyre_deg


def test_coefficients_physical_signs():
    """Test coefficient signs match physical expectations."""
    coeffs = get_default_coefficients()

    # More wing -> more downforce, more drag
    assert coeffs.downforce["front_wing"] > 0
    assert coeffs.downforce["rear_wing"] > 0
    assert coeffs.drag["front_wing"] > 0
    assert coeffs.drag["rear_wing"] > 0

    # Lower ride height -> more downforce (ground effect)
    assert coeffs.downforce["ride_height_front"] < 0
    assert coeffs.downforce["ride_height_rear"] < 0

    # More camber -> more cornering grip, more tyre wear
    assert coeffs.cornering_stiffness["front_camber"] > 0
    assert coeffs.front_tyre_deg["front_camber"] > 0

    # Higher pressure -> less wear
    assert coeffs.front_tyre_deg["tyre_pressure_front"] < 0


# ---------------------------------------------------------------------------
# Engine - Effects Computation
# ---------------------------------------------------------------------------

def test_engine_compute_effects():
    """Test SetupEngine computes effects from setup."""
    setup = create_baseline_setup(car_id="TEST", track_id="monaco")
    car = Car(
        id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
    )
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()
    effects = engine.compute_effects(setup, car, track)

    # Baseline setup should have near-zero effects
    assert abs(effects.downforce_change) < 0.01
    assert abs(effects.drag_change) < 0.01
    assert abs(effects.cornering_stiffness_change) < 0.01


def test_engine_effects_change_with_setup():
    """Test effects change when setup changes."""
    baseline = create_baseline_setup(car_id="TEST", track_id="monaco")
    high_df = create_setup_from_dict(
        {"front_wing": 8.0, "rear_wing": 8.0},
        car_id="TEST",
        track_id="monaco",
    )
    low_df = create_setup_from_dict(
        {"front_wing": 2.0, "rear_wing": 2.0},
        car_id="TEST",
        track_id="monaco",
    )

    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()
    base_effects = engine.compute_effects(baseline, car, track)
    high_effects = engine.compute_effects(high_df, car, track)
    low_effects = engine.compute_effects(low_df, car, track)

    # High downforce should increase downforce, increase drag
    assert high_effects.downforce_change > base_effects.downforce_change
    assert high_effects.drag_change > base_effects.drag_change

    # Low downforce should decrease downforce, decrease drag
    assert low_effects.downforce_change < base_effects.downforce_change
    assert low_effects.drag_change < base_effects.drag_change


def test_engine_track_modifiers():
    """Test track-specific modifiers."""
    tracks = get_2024_calendar()
    monaco = next(t for t in tracks if t.id == "monaco")
    monza = next(t for t in tracks if t.id == "monza")

    monaco_mods = get_track_modifiers(monaco)
    monza_mods = get_track_modifiers(monza)

    # Physical ordering (independent of legacy get_track_type_category labels):
    # Monza has long straights + DRS -> straight setup sensitivity higher.
    assert monza_mods["straight_factor"] > monaco_mods["straight_factor"]
    # Monaco has high slow-corner share + traction demand -> low-speed higher.
    assert monaco_mods["low_speed_factor"] > monza_mods["low_speed_factor"]
    # All factors positive and finite.
    for mods in (monaco_mods, monza_mods):
        for k in ("high_speed_factor", "low_speed_factor", "straight_factor", "braking_factor", "traction_factor"):
            assert mods[k] > 0


def test_engine_apply_to_car():
    """Test applying effects to car."""
    setup = create_setup_from_dict(
        {"front_wing": 8.0, "rear_wing": 8.0},
        car_id="TEST",
        track_id="monaco",
    )
    car = Car(
        id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024,
        overall_downforce=75, front_downforce=75, rear_downforce=75,
    )
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()
    effects = engine.compute_effects(setup, car, track)
    new_car = engine.apply_to_car(car, effects)

    # Car should be modified
    assert new_car.overall_downforce != car.overall_downforce
    assert new_car.front_downforce != car.front_downforce
    assert new_car.rear_downforce != car.rear_downforce


def test_engine_evidence_summary():
    """Test engine reports evidence tiers."""
    engine = SetupEngine()
    summary = engine.get_effect_evidence_summary()

    assert summary["aero"] == "PRIOR_ONLY"
    assert summary["mechanical"] == "PRIOR_ONLY"
    assert summary["tyre_interaction"] == "NON_IDENTIFIABLE"
    assert summary["track_interaction"] == "PRIOR_ONLY"


# ---------------------------------------------------------------------------
# Integration with LapTimeModel
# ---------------------------------------------------------------------------

def test_setup_aware_lap_time_model():
    """Test SetupAwareLapTimeModel includes setup effects."""
    from app.simulation.lap_time.model import LapTimeInputs
    from app.simulation.models.driver import Driver
    from app.simulation.models.tyre import get_standard_tyre_specs, TyreCompound
    from app.simulation.models.weather import WeatherState, WeatherCondition

    setup = create_setup_from_dict(
        {"front_wing": 8.0, "rear_wing": 8.0},
        car_id="TEST",
        track_id="monaco",
    )
    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    driver = Driver(
        id="D01", name="Test", short_name="TST", number=1, nationality="TEST",
        team_id="TEST", date_of_birth="1997-09-30",
    )
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")
    specs = get_standard_tyre_specs()
    tyre_spec = specs[TyreCompound.MEDIUM]
    weather = WeatherState(condition=WeatherCondition.DRY, air_temperature=25.0, track_temperature=35.0)

    base_inputs = LapTimeInputs(
        base_lap_time=track.reference_lap_time,
        car=car,
        engine_power_kw=750.0,
        driver=driver,
        driver_effective_skill=75.0,
        compound=TyreCompound.MEDIUM,
        tyre_spec=tyre_spec,
        tyre_age_laps=5,
        tyre_wear=0.2,
        tyre_temp=90.0,
        fuel_mass=50.0,
        fuel_per_lap=1.8,
        track=track,
        track_evolution=0.5,
        track_grip=1.0,
        weather=weather,
    )

    model = SetupAwareLapTimeModel(setup_evidence_tier=EvidenceTier.PRIOR_ONLY)

    # Without setup
    comp_no_setup = model.calculate_lap_time(base_inputs)

    # With setup
    comp_with_setup = model.calculate_lap_time_with_setup(base_inputs, setup=setup)

    # Setup should affect lap time
    assert comp_with_setup.total != comp_no_setup.total
    # The difference should be in car_delta (since we embed setup there)
    assert comp_with_setup.car_delta != comp_no_setup.car_delta


def test_compute_setup_lap_time_delta():
    """Test setup lap time delta computation."""
    setup = create_setup_from_dict(
        {"front_wing": 8.0, "rear_wing": 8.0},
        car_id="TEST",
        track_id="monaco",
    )
    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    delta = compute_setup_lap_time_delta(
        setup, car, track, base_lap_time=90.0,
        evidence_tier=EvidenceTier.PRIOR_ONLY,
    )

    assert "aero_contribution_sec" in delta
    assert "mechanical_contribution_sec" in delta
    assert "tyre_contribution_sec" in delta
    assert "total_contribution_sec" in delta
    assert delta["evidence_tier"] == "PRIOR_ONLY"


# ---------------------------------------------------------------------------
# Evidence Tiers
# ---------------------------------------------------------------------------

def test_evidence_tiers_enum():
    """Test all evidence tiers exist."""
    tiers = [e.value for e in EvidenceTier]
    assert "CALIBRATED" in tiers
    assert "LIMITED" in tiers
    assert "PRIOR_ONLY" in tiers
    assert "NON_IDENTIFIABLE" in tiers
    assert "NOT_AVAILABLE" in tiers


def test_setup_evidence_summary():
    """Test SetupEvidence summary generation."""
    evidence = SetupEvidence(
        overall_tier=EvidenceTier.PRIOR_ONLY,
        parameter_tiers={
            "front_wing": EvidenceTier.PRIOR_ONLY,
            "rear_wing": EvidenceTier.PRIOR_ONLY,
            "tyre_pressure_front": EvidenceTier.NON_IDENTIFIABLE,
        },
        limitations=["No historical data", "Tyre effects not identifiable"],
    )
    summary = evidence.get_summary()
    assert "Calibrated: 0/3" in summary
    assert "Prior-only: 2/3" in summary
    assert "Non-identifiable: 1/3" in summary


# ---------------------------------------------------------------------------
# Ablation - Setup Disabled
# ---------------------------------------------------------------------------

def test_ablation_setup_disabled_reproduces_baseline():
    """Test that setup disabled reproduces baseline behavior."""
    from app.simulation.race_engine_v20 import SetupAwareRaceEngine
    from app.data.scenario import build_scenario
    from app.simulation.scenario_v14 import ScenarioResolver
    import json

    DATA_ROOT = __file__.replace("test_phase20_setup.py", "data")
    import pathlib
    DATA_ROOT = pathlib.Path(__file__).parent.parent / "data"

    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scen = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scen.race_distance["laps"] = 5

    eng = SetupAwareRaceEngine(seed=42, setup_enabled=False)

    # Setup disabled
    scen_off = scen.model_copy(deep=True)
    scen_off.hypothetical_modifiers = {"setup": {"enabled": False}}
    r_off = eng.simulate(scen_off, simulations=20, seed=42)

    # Setup enabled with baseline
    scen_on = scen.model_copy(deep=True)
    scen_on.hypothetical_modifiers = {"setup": {"enabled": True}}
    r_on = eng.simulate(scen_on, simulations=20, seed=42)

    # Both should produce valid results
    for did in r_off["drivers"]:
        assert 0 <= r_off["drivers"][did]["win_probability"] <= 1
        assert 0 <= r_on["drivers"][did]["win_probability"] <= 1

    # Provenance should reflect setup status
    assert r_off["provenance"]["setup_enabled"] is False
    assert r_on["provenance"]["setup_enabled"] is True


# ---------------------------------------------------------------------------
# Vectorized integration (§33 dead-code check: setup must reach race engine)
# ---------------------------------------------------------------------------

def _load_bahrain_scenario(laps=8):
    import json, pathlib
    DATA_ROOT = pathlib.Path(__file__).parent.parent / "data"
    from app.data.scenario import build_scenario
    from app.simulation.scenario_v14 import ScenarioResolver
    races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    scen = ScenarioResolver.from_historical(hist, race_date=race["date"])
    scen.race_distance["laps"] = laps
    return scen


def test_setup_vectorized_baseline_preserves_legacy():
    """Setup enabled with baseline (no params) must equal setup disabled exactly."""
    from app.simulation.race_engine_v20 import SetupAwareRaceEngine
    eng = SetupAwareRaceEngine(seed=42)
    s_off = _load_bahrain_scenario(laps=8)
    s_off.hypothetical_modifiers = {"setup": {"enabled": False}}
    r_off = eng.simulate(s_off, simulations=60, seed=42)
    s_on = _load_bahrain_scenario(laps=8)
    s_on.hypothetical_modifiers = {"setup": {"enabled": True}}  # no params -> baseline
    r_on = eng.simulate(s_on, simulations=60, seed=42)
    for did in r_off["drivers"]:
        assert abs(r_off["drivers"][did]["win_probability"] - r_on["drivers"][did]["win_probability"]) < 1e-12
    # Offsets must be empty/zero in both cases
    assert r_on["setup_model"]["offsets_sec_per_lap"] == {}


def test_setup_vectorized_per_driver_change_moves_outcome():
    """One driver with lower ride height (faster prior) must change outcome + fingerprint."""
    from app.simulation.race_engine_v20 import SetupAwareRaceEngine
    eng = SetupAwareRaceEngine(seed=42)
    s_base = _load_bahrain_scenario(laps=10)
    s_base.hypothetical_modifiers = {"setup": {"enabled": True}}
    r_base = eng.simulate(s_base, simulations=100, seed=42)

    s_mod = _load_bahrain_scenario(laps=10)
    # Pick first driver and give lower ride heights (more ground effect, less drag in prior)
    first_driver = s_mod.drivers[0]["driver_id"]
    s_mod.hypothetical_modifiers = {
        "setup": {
            "enabled": True,
            "mode": "counterfactual",
            "drivers": {first_driver: {"ride_height_front": 15.0, "ride_height_rear": 25.0}},
        }
    }
    r_mod = eng.simulate(s_mod, simulations=100, seed=42)

    offs = r_mod["setup_model"]["offsets_sec_per_lap"]
    assert first_driver in offs
    assert offs[first_driver] < -0.05  # faster by >50ms/lap in prior
    # Fingerprint must change
    fp_base = r_base["provenance"].get("setup_fingerprints", {})
    fp_mod = r_mod["provenance"].get("setup_fingerprints", {})
    assert fp_base != fp_mod
    # Outcome distribution must move somewhere in the field (continuous metric).
    # Win probs are coarse at N=100 (1% granularity) and may saturate for the
    # leader, so compare expected finishing position of the treated driver
    # plus the max win-prob move across the field.
    e_base = r_base["drivers"][first_driver]["expected_finish"]
    e_mod = r_mod["drivers"][first_driver]["expected_finish"]
    max_move = max(
        abs(r_mod["drivers"][d]["win_probability"] - r_base["drivers"][d]["win_probability"])
        for d in r_base["drivers"]
    )
    assert (abs(e_mod - e_base) > 1e-9) or (max_move > 0)
    # Determinism: repeat identical setup -> identical win prob
    s_mod2 = _load_bahrain_scenario(laps=10)
    s_mod2.hypothetical_modifiers = s_mod.hypothetical_modifiers
    r_mod2 = eng.simulate(s_mod2, simulations=100, seed=42)
    assert abs(r_mod["drivers"][first_driver]["win_probability"] - r_mod2["drivers"][first_driver]["win_probability"]) < 1e-12


# ---------------------------------------------------------------------------
# Counterfactual API
# ---------------------------------------------------------------------------

def test_counterfactual_setup_comparison():
    """Test comparing baseline vs modified setup."""
    baseline = create_baseline_setup(car_id="TEST", track_id="monaco")
    modified = create_setup_from_dict(
        {"rear_wing": 3.0},  # Lower rear wing
        car_id="TEST",
        track_id="monaco",
    )

    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()
    base_effects = engine.compute_effects(baseline, car, track)
    mod_effects = engine.compute_effects(modified, car, track)

    base_delta = engine.compute_lap_time_delta(base_effects, 90.0, track)
    mod_delta = engine.compute_lap_time_delta(mod_effects, 90.0, track)

    # Lower rear wing should reduce drag, reduce downforce
    assert mod_effects.drag_change < base_effects.drag_change
    assert mod_effects.downforce_change < base_effects.downforce_change


# ---------------------------------------------------------------------------
# Sensitivity / Perturbation
# ---------------------------------------------------------------------------

def test_perturb_setup_parameter():
    """Test perturbing a single setup parameter."""
    baseline = create_baseline_setup(car_id="TEST", track_id="monaco")

    # Perturb rear_wing by -2
    perturbed = create_setup_from_dict(
        {"rear_wing": baseline.parameters.rear_wing.value - 2.0},
        car_id="TEST",
        track_id="monaco",
    )

    # Should have different fingerprint
    assert baseline.fingerprint != perturbed.fingerprint

    # Deviation should show the change
    deviations = perturbed.get_baseline_deviation()
    assert abs(deviations["rear_wing"] - (-2.0)) < 0.01


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_setup_deterministic_effects():
    """Test setup effects are deterministic."""
    setup = create_setup_from_dict(
        {"front_wing": 7.0, "rear_wing": 6.0},
        car_id="TEST",
        track_id="monaco",
    )
    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()
    effects1 = engine.compute_effects(setup, car, track)
    effects2 = engine.compute_effects(setup, car, track)

    assert effects1.downforce_change == effects2.downforce_change
    assert effects1.drag_change == effects2.drag_change
    assert effects1.cornering_stiffness_change == effects2.cornering_stiffness_change


def test_setup_fingerprint_reproducible():
    """Test fingerprint is reproducible across runs."""
    setup1 = create_baseline_setup(car_id="RB20", track_id="monaco", mode=SetupMode.HISTORICAL)
    setup2 = create_baseline_setup(car_id="RB20", track_id="monaco", mode=SetupMode.HISTORICAL)

    assert setup1.fingerprint == setup2.fingerprint


# ---------------------------------------------------------------------------
# Leakage - No Future Information
# ---------------------------------------------------------------------------

def test_leakage_no_future_setup_in_historical():
    """Test historical mode doesn't use future setup info."""
    # Historical setup should be baseline (no historical data available)
    historical = create_baseline_setup(
        car_id="RB20",
        track_id="monaco",
        mode=SetupMode.HISTORICAL,
    )

    # Evidence should reflect lack of historical data
    assert historical.evidence.overall_tier in (
        EvidenceTier.PRIOR_ONLY,
        EvidenceTier.NON_IDENTIFIABLE,
    )
    assert any("historical" in lim.lower() or "no historical" in lim.lower()
               for lim in historical.evidence.limitations)


def test_leakage_counterfactual_labeled():
    """Test counterfactual setups are labeled correctly."""
    counterfactual = create_setup_from_dict(
        {"rear_wing": 3.0},
        car_id="RB20",
        track_id="monaco",
        mode=SetupMode.COUNTERFACTUAL,
    )

    assert counterfactual.mode == SetupMode.COUNTERFACTUAL
    # Fingerprint should differ from baseline
    baseline = create_baseline_setup(car_id="RB20", track_id="monaco")
    assert counterfactual.fingerprint != baseline.fingerprint


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_setup_provenance():
    """Test setup carries provenance."""
    setup = create_baseline_setup(car_id="TEST", track_id="monaco")

    assert "created_at" in setup.provenance
    assert setup.provenance["source"] == "phase20_baseline_factory"
    assert setup.provenance["car_id"] == "TEST"


def test_setup_scenario_modifier():
    """Test setup can be converted to scenario modifier."""
    setup = create_setup_from_dict(
        {"front_wing": 7.0, "rear_wing": 5.0},
        car_id="TEST",
        track_id="monaco",
        mode=SetupMode.HYPOTHETICAL,
    )

    modifier = setup.to_scenario_modifier()

    assert "setup" in modifier
    assert modifier["setup"]["setup_id"] == setup.setup_id
    assert modifier["setup"]["parameters"]["front_wing"] == 7.0
    assert modifier["setup"]["parameters"]["rear_wing"] == 5.0
    assert modifier["setup"]["fingerprint"] == setup.fingerprint


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

def test_setup_engine_performance():
    """Test setup engine performance is reasonable."""
    import time

    setup = create_baseline_setup(car_id="TEST", track_id="monaco")
    car = Car(id="TEST", name="Test", team_id="TEST", engine_id="TEST", year=2024)
    tracks = get_2024_calendar()
    track = next(t for t in tracks if t.id == "monaco")

    engine = SetupEngine()

    # Time multiple computations
    start = time.perf_counter()
    for _ in range(1000):
        engine.compute_effects(setup, car, track)
    elapsed = time.perf_counter() - start

    # Should be fast (< 1s for 1000 computations; ~0.1ms each).
    # Threshold relaxed for Windows CI variance; measures no blowup, not tuning.
    assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])