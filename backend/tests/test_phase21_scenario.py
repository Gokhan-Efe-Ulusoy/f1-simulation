"""Phase 21 — Counterfactual & Scenario Engine tests.

Convention: 2024-bahrain historical baseline, shortened races, vectorized
path (N>=50) for propagation. Shared baseline legs are cached per module to
keep suite runtime sane; every cached reuse is same-seed/same-N (CRN-safe).
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent / "data"

from app.data.scenario import build_scenario
from app.simulation.scenario_v14 import ScenarioResolver
from app.simulation.scenario.models import (
    Intervention,
    ScenarioSpec,
)
from app.simulation.scenario.engine import ScenarioEngine
from app.simulation.scenario.compiler import (
    baseline_fingerprint,
    compile_spec,
    scenario_content_hash,
    spec_fingerprint,
)
from app.simulation.scenario.comparison import compare_results
from app.simulation.scenario.validation import (
    ScenarioValidationError,
    validate_intervention,
    validate_spec,
)


def _baseline(laps=6):
    races = json.loads((ROOT / "canonical" / "races.json").read_text())
    race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
    results = json.loads((ROOT / "canonical" / "results.json").read_text())
    race_results = [res for res in results if res["race_id"] == race["race_id"]]
    hist = build_scenario(race, race_results)
    sc = ScenarioResolver.from_historical(hist, race_date=race["date"])
    sc.race_distance["laps"] = laps
    return sc


_BASELINE_CACHE: dict = {}


def _baseline_leg(laps=6, sims=60, seed=42):
    key = (laps, sims, seed)
    if key not in _BASELINE_CACHE:
        eng = ScenarioEngine(seed=seed, simulations=sims)
        _BASELINE_CACHE[key] = eng.run_baseline(_baseline(laps), simulations=sims, seed=seed)
    return _BASELINE_CACHE[key]


def _spec(idsuf, ivs, laps=6, sims=60, seed=42, stype="counterfactual"):
    sc = _baseline(laps)
    return sc, ScenarioSpec(
        spec_id=f"p21-{idsuf}", baseline_scenario_id=sc.scenario_id,
        scenario_type=stype, interventions=list(ivs), seed=seed, simulations=sims,
    )


def _cf_leg(sc, spec):
    eng = ScenarioEngine()
    _, _, _, result = eng.run_counterfactual(sc, spec)
    return result


# ---------------------------------------------------------------------------
# Models & registry
# ---------------------------------------------------------------------------

def test_intervention_model_serialization():
    iv = Intervention(family="setup", op="SET_VALUE", target="VER", parameter="rear_wing", value=5.0)
    d = iv.model_dump()
    iv2 = Intervention(**d)
    assert iv2.key() == ("setup", "VER", "rear_wing")
    assert "rear_wing" in iv.describe()


def test_spec_serialization_roundtrip():
    sc, spec = _spec("rt", [Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=2.0)])
    d = spec.model_dump()
    spec2 = ScenarioSpec(**d)
    assert spec2.spec_id == spec.spec_id
    assert len(spec2.interventions) == 1
    assert spec2.interventions[0].parameter == "rainfall_mm_h"


def test_registry_consistency():
    from app.simulation.scenario.registry import (
        FAMILY_OPS, FAMILY_PARAMS, FAMILY_TIERS, PATHWAYS, SETUP_PARAMS,
    )
    assert len(SETUP_PARAMS) == 18  # mirrors Phase 20 SetupParameters
    for fam, ops in FAMILY_OPS.items():
        assert fam in FAMILY_PARAMS and fam in FAMILY_TIERS and fam in PATHWAYS
        assert len(ops) >= 1 and len(PATHWAYS[fam]) >= 2


def test_leakage_blocklist_hits():
    from app.simulation.scenario.registry import is_leakage_param
    for bad in ["future_result", "actual_winner", "finishing_position", "result", "as_of", "observed_weather"]:
        assert is_leakage_param(bad), bad
    for good in ["rear_wing", "rainfall_mm_h", "pit_laps", "pace_delta", "enable_vsc"]:
        assert not is_leakage_param(good), good


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_valid_interventions_pass():
    sc = _baseline()
    did = sc.drivers[0]["driver_id"]
    cid = sc.drivers[0].get("constructor_id", "")
    cases = [
        Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=7.0),
        Intervention(family="setup", op="ADD_DELTA", target="all", parameter="front_wing", value=1.0),
        Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[3]),
        Intervention(family="tyre", op="SET_VALUE", target=did, parameter="starting_compound", value="MEDIUM"),
        Intervention(family="race_control", op="DISABLE", target="race", parameter="enable_vsc", value=None),
        Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=5.0),
        Intervention(family="driver", op="ADD_DELTA", target=did, parameter="pace_delta", value=0.5),
        Intervention(family="car", op="ADD_DELTA", target=cid, parameter="pace_delta", value=-0.5),
    ]
    for iv in cases:
        errs, _, _ = validate_intervention(iv, sc)
        assert errs == [], (iv.describe(), errs)


def test_unknown_parameter_rejected():
    sc = _baseline()
    iv = Intervention(family="setup", op="SET_VALUE", target="all", parameter="warp_drive", value=1.0)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("unknown parameter" in e for e in errs)


def test_unknown_driver_rejected():
    sc = _baseline()
    iv = Intervention(family="driver", op="ADD_DELTA", target="NOPE", parameter="pace_delta", value=0.5)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("unknown driver" in e for e in errs)


def test_unknown_track_target_rejected():
    sc = _baseline()
    iv = Intervention(family="setup", op="SET_VALUE", target="monza-1960", parameter="rear_wing", value=5.0)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("unknown target" in e for e in errs)


def test_out_of_range_setup_rejected():
    sc = _baseline()
    iv = Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=99.0)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("out of model bounds" in e for e in errs)


def test_invalid_type_rejected():
    sc = _baseline()
    iv = Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value="lots")
    errs, _, _ = validate_intervention(iv, sc)
    assert any("numeric" in e for e in errs)


def test_bad_op_rejected():
    sc = _baseline()
    iv = Intervention(family="driver", op="SET_VALUE", target=sc.drivers[0]["driver_id"], parameter="pace_delta", value=1.0)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("not allowed" in e for e in errs)


def test_forced_rc_event_rejected():
    sc = _baseline()
    iv = Intervention(family="race_control", op="SET_VALUE", target="race", parameter="force_safety_car_lap", value=10)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("unknown parameter" in e for e in errs)


def test_rc_threshold_out_of_range_rejected():
    sc = _baseline()
    iv = Intervention(family="race_control", op="SET_VALUE", target="race", parameter="wetness_red_flag_threshold", value=5.0)
    errs, _, _ = validate_intervention(iv, sc)
    assert any("out of range" in e for e in errs)


def test_future_leakage_param_rejected():
    sc = _baseline()
    for bad in ["future_result", "actual_winner", "finishing_position", "observed_weather"]:
        iv = Intervention(family="weather", op="SET_VALUE", target="race", parameter=bad, value=1.0)
        errs, _, _ = validate_intervention(iv, sc)
        assert errs, bad


def test_conflicting_interventions_rejected():
    sc = _baseline()
    did = sc.drivers[0]["driver_id"]
    spec = ScenarioSpec(
        spec_id="p21-conf", baseline_scenario_id=sc.scenario_id,
        interventions=[
            Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=4.0),
            Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=6.0),
        ],
    )
    errs, _ = validate_spec(spec, sc)
    assert any("conflicting" in e for e in errs)


def test_pit_stints_conflict_rejected():
    sc = _baseline()
    did = sc.drivers[0]["driver_id"]
    spec = ScenarioSpec(
        spec_id="p21-conf2", baseline_scenario_id=sc.scenario_id,
        interventions=[
            Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[3]),
            Intervention(family="tyre", op="SET_VALUE", target=did, parameter="stints",
                         value=[{"compound": "SOFT", "laps": 3}, {"compound": "HARD", "laps": 3}]),
        ],
    )
    errs, _ = validate_spec(spec, sc)
    assert any("conflicting" in e for e in errs)


def test_unsupported_strategy_policy_rejected():
    sc = _baseline()
    iv = Intervention(family="strategy", op="SET_VALUE", target="all", parameter="policy", value="aggressive")
    errs, _, _ = validate_intervention(iv, sc)
    assert any("unknown parameter" in e for e in errs)


def test_era_unknown_flagged_not_rejected():
    from app.data.scenario import build_scenario as _bs
    import json as _json
    races = _json.loads((ROOT / "canonical" / "races.json").read_text())
    old = [r for r in races if r["season_id"] < "2000"][0]
    results = _json.loads((ROOT / "canonical" / "results.json").read_text())
    hist = _bs(old, [res for res in results if res["race_id"] == old["race_id"]])
    sc = ScenarioResolver.from_historical(hist, race_date=old["date"])
    iv = Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=6.0)
    errs, warns, ctx = validate_intervention(iv, sc)
    assert errs == []
    assert ctx.get("era_status") == "UNKNOWN"
    assert any("unknown" in w.lower() for w in warns)


# ---------------------------------------------------------------------------
# Compiler: immutability, application, fingerprints
# ---------------------------------------------------------------------------

def test_compiler_does_not_mutate_baseline():
    sc = _baseline()
    before = sc.model_dump()
    spec = ScenarioSpec(
        spec_id="p21-imm", baseline_scenario_id=sc.scenario_id,
        interventions=[Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=8.0)],
    )
    compile_spec(sc, spec)
    assert sc.model_dump() == before


def test_compiler_applies_namespaces_and_order():
    sc = _baseline()
    did = sc.drivers[0]["driver_id"]
    spec = ScenarioSpec(
        spec_id="p21-ns", baseline_scenario_id=sc.scenario_id,
        interventions=[
            Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=8.0),
            Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=3.0),
            Intervention(family="race_control", op="DISABLE", target="race", parameter="enable_vsc", value=None),
        ],
    )
    comp, trace, _ = compile_spec(sc, spec)
    assert comp.hypothetical_modifiers["setup"]["drivers"][did]["rear_wing"] == 8.0
    assert comp.hypothetical_modifiers["weather"]["rainfall_mm_h"] == 3.0
    assert comp.hypothetical_modifiers["race_control"]["enable_vsc"] is False
    assert comp.type == "counterfactual"
    assert [t.parameter for t in trace] == ["rear_wing", "rainfall_mm_h", "enable_vsc"]
    # baseline untouched by compile
    assert "rear_wing" not in str(sc.hypothetical_modifiers.get("setup", {}))


def test_constructor_target_expands_to_members():
    sc = _baseline()
    cid = sc.drivers[0].get("constructor_id", "")
    members = [d["driver_id"] for d in sc.drivers if d.get("constructor_id") == cid]
    assert len(members) >= 1
    spec = ScenarioSpec(
        spec_id="p21-exp", baseline_scenario_id=sc.scenario_id,
        interventions=[Intervention(family="setup", op="SET_VALUE", target=cid, parameter="front_wing", value=7.0)],
    )
    comp, trace, _ = compile_spec(sc, spec)
    got = comp.hypothetical_modifiers["setup"]["drivers"]
    for m in members:
        assert got[m]["front_wing"] == 7.0


def test_empty_spec_compiles_to_baseline_copy():
    sc = _baseline()
    spec = ScenarioSpec(spec_id="p21-empty", baseline_scenario_id=sc.scenario_id, interventions=[])
    comp, trace, warns = compile_spec(sc, spec)
    assert trace == []
    assert comp.scenario_id == sc.scenario_id
    assert comp is not sc


def test_fingerprint_changes_and_reproduces():
    sc = _baseline()
    did = sc.drivers[0]["driver_id"]
    mk = lambda v: ScenarioSpec(
        spec_id="p21-fp", baseline_scenario_id=sc.scenario_id,
        interventions=[Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=v)],
        seed=42, simulations=60,
    )
    bfp = baseline_fingerprint(sc)
    f1 = spec_fingerprint(mk(4.0), scenario_content_hash(sc))
    f2 = spec_fingerprint(mk(4.0), scenario_content_hash(sc))
    f3 = spec_fingerprint(mk(5.0), scenario_content_hash(sc))
    assert f1 == f2 and f1 != f3 and f1 != bfp
    assert len(f1) == 16


def test_branch_specs_share_baseline():
    sc = _baseline()
    from app.simulation.scenario.compiler import build_branch_specs
    specs = build_branch_specs(sc.scenario_id, "p21-br", {
        "A": [Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=3.0)],
        "B": [Intervention(family="race_control", op="DISABLE", target="race", parameter="enabled", value=None)],
    })
    assert [s.spec_id for s in specs] == ["p21-br-A", "p21-br-B"]
    assert all(s.baseline_scenario_id == sc.scenario_id for s in specs)


# ---------------------------------------------------------------------------
# Baseline preservation & ablation
# ---------------------------------------------------------------------------

def test_baseline_preservation_empty_spec():
    sc = _baseline(laps=6)
    eng = ScenarioEngine(seed=42, simulations=60)
    direct = eng.run_baseline(sc, simulations=60, seed=42)
    spec = ScenarioSpec(spec_id="p21-pres", baseline_scenario_id=sc.scenario_id, interventions=[],
                        seed=42, simulations=60)
    res = eng.run_spec(sc, spec)
    for did in direct["drivers"]:
        assert abs(direct["drivers"][did]["win_probability"] - res.comparison.driver_effects[
            [e.driver_id for e in res.comparison.driver_effects].index(did)
        ].baseline_win_probability) < 1e-12
    assert all(abs(e.d_win_probability) < 1e-12 for e in res.comparison.driver_effects)


def test_ablation_empty_vs_intervention():
    sc, spec = _spec("abl", [Intervention(
        family="driver", op="ADD_DELTA", target=_baseline().drivers[0]["driver_id"],
        parameter="pace_delta", value=1.0)], laps=6, sims=60)
    eng = ScenarioEngine()
    res = eng.run_spec(sc, spec)
    moves = [e for e in res.comparison.driver_effects if abs(e.l1_finish_distribution) > 0]
    assert moves, "intervention must move at least one driver distribution"
    # empty spec on same baseline moves nothing (covered above); provenance differs
    assert res.baseline_fingerprint != res.counterfactual_fingerprint


# ---------------------------------------------------------------------------
# Propagation per family (vectorized, N=60, CRN)
# ---------------------------------------------------------------------------

def _propagate(name, ivs, laps=6, sims=60):
    sc, spec = _spec(f"prop-{name}", ivs, laps=laps, sims=sims)
    eng = ScenarioEngine()
    res = eng.run_spec(sc, spec)
    base = _BASELINE_CACHE.get((laps, sims, 42))
    if base is None:
        base = eng.run_baseline(_baseline(laps), simulations=sims, seed=42)
        _BASELINE_CACHE[(laps, sims, 42)] = base
    return res, base


def test_propagate_setup():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("setup", [Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=1.0)])
    eff = {e.driver_id: e for e in res.comparison.driver_effects}[did]
    assert eff.l1_finish_distribution > 0
    assert res.trace[0].modifier_path.endswith(f"drivers.{did}.rear_wing")


def test_propagate_race_control_disable():
    res, _ = _propagate("rc", [Intervention(family="race_control", op="DISABLE", target="race", parameter="enabled", value=None)])
    moves = [e for e in res.comparison.driver_effects if e.l1_finish_distribution > 0]
    assert moves, "RC disable must change neutralization exposure/outcome"
    assert "race_control" in res.comparison.race_effects


def test_propagate_weather_wet():
    res, _ = _propagate("wx", [Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=8.0)])
    moves = [e for e in res.comparison.driver_effects if e.l1_finish_distribution > 0]
    assert moves, "wet-weather override must change grip/pace"
    assert "weather" in res.comparison.race_effects


def test_propagate_tyre_compound():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("tyre", [Intervention(family="tyre", op="SET_VALUE", target=did, parameter="starting_compound", value="MEDIUM")])
    eff = {e.driver_id: e for e in res.comparison.driver_effects}[did]
    assert eff.l1_finish_distribution > 0


def test_propagate_strategy_pit_laps():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("pit", [Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[3])])
    eff = {e.driver_id: e for e in res.comparison.driver_effects}[did]
    assert eff.l1_finish_distribution > 0
    assert any("Pit stops carry no time loss" in a for a in res.explanation.assumptions)


def test_propagate_driver_pace():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("pace", [Intervention(family="driver", op="ADD_DELTA", target=did, parameter="pace_delta", value=1.0)])
    eff = {e.driver_id: e for e in res.comparison.driver_effects}[did]
    assert eff.l1_finish_distribution > 0


def test_propagate_car_pace():
    sc0 = _baseline()
    cid = sc0.drivers[0].get("constructor_id", "")
    res, _ = _propagate("car", [Intervention(family="car", op="ADD_DELTA", target=cid, parameter="pace_delta", value=1.0)])
    moves = [e for e in res.comparison.driver_effects if e.l1_finish_distribution > 0]
    assert moves


def test_propagate_stints_form():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("stints", [Intervention(
        family="tyre", op="SET_VALUE", target=did, parameter="stints",
        value=[{"compound": "SOFT", "laps": 3}, {"compound": "HARD", "laps": 3}])])
    eff = {e.driver_id: e for e in res.comparison.driver_effects}[did]
    assert eff.l1_finish_distribution > 0


def test_multiple_simultaneous_interventions():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("multi", [
        Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=3.0),
        Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[3]),
        Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=4.0),
    ])
    assert len(res.trace) == 3
    assert set(res.explanation.pathways) == {"setup", "strategy", "weather"}
    moves = [e for e in res.comparison.driver_effects if e.l1_finish_distribution > 0]
    assert moves


# ---------------------------------------------------------------------------
# Leakage (adversarial)
# ---------------------------------------------------------------------------

def test_leakage_future_result_rejected_at_validation():
    sc = _baseline()
    spec = ScenarioSpec(
        spec_id="p21-leak", baseline_scenario_id=sc.scenario_id,
        interventions=[Intervention(family="weather", op="SET_VALUE", target="race", parameter="future_result", value=1.0)],
    )
    with pytest.raises(ScenarioValidationError):
        compile_spec(sc, spec)


def test_leakage_junk_modifiers_ignored_by_engine():
    sc, spec = _spec("junk", [Intervention(
        family="setup", op="SET_VALUE", target=_baseline().drivers[0]["driver_id"],
        parameter="front_wing", value=8.0)], laps=6, sims=60)
    comp, _, _ = compile_spec(sc, spec)
    comp.hypothetical_modifiers["future_result"] = {"winner": "VER"}
    comp.hypothetical_modifiers["realized_weather"] = {"rain": 99}
    eng = ScenarioEngine()
    r_junk = eng._simulate(comp, 60, 42)
    comp2, _, _ = compile_spec(sc, spec)
    r_clean = eng._simulate(comp2, 60, 42)
    for did in r_clean["drivers"]:
        assert abs(r_clean["drivers"][did]["win_probability"] - r_junk["drivers"][did]["win_probability"]) < 1e-12


def test_leakage_future_weather_realized_ignored():
    # Even if a caller hand-injects a 'realized' weather block, the weather
    # engine only honours known initial-state fields; unknown keys are inert.
    sc, spec = _spec("wdisc", [], laps=6, sims=60)
    comp, _, _ = compile_spec(sc, spec)
    comp.hypothetical_modifiers["weather"] = {"realized_rain_lap10": 50.0}
    eng = ScenarioEngine()
    r = eng._simulate(comp, 60, 42)
    base = _baseline_leg(6, 60, 42)
    for did in base["drivers"]:
        assert abs(base["drivers"][did]["win_probability"] - r["drivers"][did]["win_probability"]) < 1e-12


# ---------------------------------------------------------------------------
# Determinism, RNG isolation, branching, extremes
# ---------------------------------------------------------------------------

def test_determinism_small_n():
    sc = _baseline(laps=5)
    eng = ScenarioEngine(seed=7, simulations=10)
    r1 = eng.run_baseline(sc, simulations=10, seed=7)
    r2 = eng.run_baseline(sc, simulations=10, seed=7)
    for did in r1["drivers"]:
        assert r1["drivers"][did]["win_probability"] == r2["drivers"][did]["win_probability"]


def test_determinism_counterfactual():
    sc, spec = _spec("det", [Intervention(
        family="race_control", op="DISABLE", target="race", parameter="enable_safety_car", value=None)],
        laps=6, sims=60)
    eng = ScenarioEngine()
    a = eng.run_spec(sc, spec)
    b = eng.run_spec(sc, spec)
    assert a.counterfactual_fingerprint == b.counterfactual_fingerprint
    da = {e.driver_id: e.d_win_probability for e in a.comparison.driver_effects}
    db = {e.driver_id: e.d_win_probability for e in b.comparison.driver_effects}
    assert da == db


def test_different_seed_changes_stochastic_output():
    sc = _baseline(laps=6)
    eng = ScenarioEngine()
    r1 = eng.run_baseline(sc, simulations=60, seed=42)
    r2 = eng.run_baseline(sc, simulations=60, seed=43)
    assert any(r1["drivers"][d]["win_probability"] != r2["drivers"][d]["win_probability"] for d in r1["drivers"])


def test_rng_isolation_baseline_leg_stable():
    # Baseline leg of two different counterfactuals (same seed) is identical:
    # the intervention touches no unrelated RNG stream.
    sc = _baseline(laps=6)
    eng = ScenarioEngine()
    sc_a, spec_a = _spec("isoA", [Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=3.0)], laps=6, sims=60)
    sc_b, spec_b = _spec("isoB", [Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=6.0)], laps=6, sims=60)
    ra = eng.run_spec(sc_a, spec_a)
    rb = eng.run_spec(sc_b, spec_b)
    ea = {e.driver_id: e.baseline_win_probability for e in ra.comparison.driver_effects}
    eb = {e.driver_id: e.baseline_win_probability for e in rb.comparison.driver_effects}
    assert ea == eb


def test_branching_shared_baseline():
    sc = _baseline(laps=5)
    did = sc.drivers[0]["driver_id"]
    eng = ScenarioEngine(seed=42, simulations=60)
    out = eng.run_branch(sc, {
        "A": [Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=3.0)],
        "B": [Intervention(family="race_control", op="DISABLE", target="race", parameter="enabled", value=None)],
        "C": [Intervention(family="driver", op="ADD_DELTA", target=did, parameter="pace_delta", value=0.5)],
    }, seed=42, simulations=60)
    assert set(out) == {"A", "B", "C"}
    fps = {out[k].counterfactual_fingerprint for k in out}
    assert len(fps) == 3  # distinct interventions -> distinct fingerprints
    base_fp = {out[k].baseline_fingerprint for k in out}
    assert len(base_fp) == 1  # one shared baseline
    for k in out:
        assert out[k].comparison.common_random_numbers is True


def test_no_mutable_baseline_corruption():
    sc = _baseline(laps=6)
    before = sc.model_dump()
    eng = ScenarioEngine(seed=42, simulations=60)
    did = sc.drivers[0]["driver_id"]
    eng.run_branch(sc, {
        "A": [Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=2.0)],
        "B": [Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=7.0)],
    }, seed=42, simulations=60)
    assert sc.model_dump() == before
    # Baseline still reproduces identically afterwards.
    r1 = eng.run_baseline(sc, simulations=60, seed=42)
    base = _baseline_leg(6, 60, 42)
    for did2 in base["drivers"]:
        assert abs(base["drivers"][did2]["win_probability"] - r1["drivers"][did2]["win_probability"]) < 1e-12


def test_extreme_valid_setup_boundary():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    res, _ = _propagate("ext", [
        Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=10.0),
        Intervention(family="setup", op="SET_VALUE", target=did, parameter="brake_bias", value=65.0),
        Intervention(family="race_control", op="DISABLE", target="race", parameter="enabled", value=None),
    ], laps=6, sims=60)
    import math
    for e in res.comparison.driver_effects:
        for v in (e.d_win_probability, e.d_expected_finish, e.d_dnf_probability):
            assert math.isfinite(v)


def test_invalid_spec_raises_on_run():
    sc = _baseline()
    spec = ScenarioSpec(
        spec_id="p21-bad", baseline_scenario_id=sc.scenario_id,
        interventions=[Intervention(family="setup", op="SET_VALUE", target="all", parameter="rear_wing", value=99.0)],
    )
    eng = ScenarioEngine()
    with pytest.raises(ScenarioValidationError):
        eng.run_spec(sc, spec)


def test_malformed_spec_rejected():
    sc = _baseline()
    spec = ScenarioSpec(spec_id="p21-mm", baseline_scenario_id="wrong-id", interventions=[])
    with pytest.raises(ScenarioValidationError):
        compile_spec(sc, spec)


# ---------------------------------------------------------------------------
# Comparison & explanation structure
# ---------------------------------------------------------------------------

def test_comparison_structure_and_notes():
    sc, spec = _spec("cmp", [Intervention(
        family="driver", op="ADD_DELTA", target=_baseline().drivers[0]["driver_id"],
        parameter="pace_delta", value=0.5)], laps=6, sims=60)
    eng = ScenarioEngine()
    res = eng.run_spec(sc, spec)
    c = res.comparison
    assert c.common_random_numbers is True
    assert c.seed == 42 and c.simulations == 60
    assert len(c.driver_effects) == len(sc.drivers)
    assert c.constructor_effects
    assert c.metric_notes
    assert set(c.evidence_tiers.values()) <= {"PRIOR_ONLY", "ESTIMATED", "LIMITED", "CALIBRATED", "NON_IDENTIFIABLE"}


def test_explanation_grounded_in_trace():
    sc0 = _baseline()
    did = sc0.drivers[0]["driver_id"]
    sc, spec = _spec("expl", [
        Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=3.0),
        Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[3]),
    ], laps=6, sims=60)
    eng = ScenarioEngine()
    res = eng.run_spec(sc, spec)
    ex = res.explanation
    assert len(ex.what_changed) == 2
    assert set(ex.pathways) == {"setup", "strategy"}
    assert "causally" in ex.disclaimer
    assert ex.how_much and ex.uncertainty and ex.assumptions


def test_result_provenance_complete():
    sc, spec = _spec("prov", [Intervention(
        family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=4.0)],
        laps=6, sims=60)
    eng = ScenarioEngine()
    res = eng.run_spec(sc, spec)
    assert res.baseline_fingerprint and res.counterfactual_fingerprint
    assert res.provenance["baseline_scenario_id"] == sc.scenario_id
    assert "versions" in res.provenance
    assert res.provenance["versions"].get("SCENARIO_MODEL_VERSION") == "scenario-v1.0.0"


def test_version_bump_scenario():
    from app.simulation.version import MODEL_VERSION, SIMULATION_VERSION, RACEENGINE_VERSION, SCENARIO_MODEL_VERSION, STRATEGY_MODEL_VERSION
    assert MODEL_VERSION in ("0.8.0", "0.9.0")
    assert SIMULATION_VERSION in ("9.1.0", "9.2.0")
    assert RACEENGINE_VERSION in ("raceengine-v2.1.0", "raceengine-v2.2.0")
    assert SCENARIO_MODEL_VERSION == "scenario-v1.0.0"
    assert STRATEGY_MODEL_VERSION in ("strategy-v1.0.0", "strategy-v1.1.0")
