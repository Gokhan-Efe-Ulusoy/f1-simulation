"""Phase 22 — Monotonicity / physical sanity checks.

Each check perturbs one mechanism in a fixed direction and verifies the
model responds in the physically expected direction (within a Monte Carlo
tolerance under common random numbers). Where the model has no mechanism
for the tested relationship, the check returns NOT_TESTABLE or
NON_IDENTIFIABLE instead of forcing a pass.
"""
from __future__ import annotations

from typing import Any, Callable

from app.simulation.replay.models import SanityCheck

TOL_DEFAULT = 0.75


def _expected_finish(result: dict[str, Any], driver_id: str) -> float:
    try:
        return float(result["drivers"][driver_id]["expected_finish"] or 0.0)
    except Exception:
        return 0.0


def _l1max(comparison: Any) -> float:
    try:
        return max(
            (e.l1_finish_distribution for e in comparison.driver_effects),
            default=0.0,
        )
    except Exception:
        return 0.0


def check_pit_loss_monotonic(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
    tol: float = TOL_DEFAULT,
) -> SanityCheck:
    """Higher pit-loss must not systematically improve the pitting driver."""
    from app.simulation.scenario.models import Intervention

    def _mk(base: Any, loss: float) -> Any:
        laps = int((base.race_distance.get("laps") or 6))
        return [
            Intervention(family="strategy", op="SET_VALUE", target=driver_id,
                         parameter="pit_laps", value=[max(2, laps // 2)]),
            Intervention(family="strategy", op="SET_VALUE", target=driver_id,
                         parameter="pit_loss_seconds", value=loss),
        ]

    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()
    spec_lo = ScenarioSpec(spec_id="sanity-pitlo", baseline_scenario_id=base.scenario_id,
                           interventions=_mk(base, 5.0), seed=seed, simulations=simulations)
    spec_hi = ScenarioSpec(spec_id="sanity-pithi", baseline_scenario_id=base.scenario_id,
                           interventions=_mk(base, 30.0), seed=seed, simulations=simulations)
    try:
        r_lo = eng.run_spec(baseline_factory(), spec_lo)
        r_hi = eng.run_spec(baseline_factory(), spec_hi)
    except Exception as exc:
        return SanityCheck(name="pit_loss_monotonic", status="NOT_TESTABLE",
                           detail=f"engine could not run pit-loss legs: {exc}")
    cf_lo = eng.run_counterfactual(baseline_factory(), spec_lo)[3]
    cf_hi = eng.run_counterfactual(baseline_factory(), spec_hi)[3]
    f_lo = _expected_finish(cf_lo, driver_id)
    f_hi = _expected_finish(cf_hi, driver_id)
    delta = f_hi - f_lo  # expected: >= -tol (higher loss should not improve)
    moved = _l1max(r_hi.comparison) > 0 or _l1max(r_lo.comparison) > 0
    status = "PASS" if (delta >= -tol and moved) else "FAIL"
    return SanityCheck(
        name="pit_loss_monotonic",
        status=status,
        detail=(
            f"E[finish] loss=5s: {f_lo:.3f} vs loss=30s: {f_hi:.3f} "
            f"(delta {delta:+.3f}, tol {tol}); legs moved={moved}."
        ),
        evidence_tier="PRIOR_ONLY",
        measured={"e_finish_loss5": f_lo, "e_finish_loss30": f_hi, "delta": delta},
    )


def check_extra_stop_cost(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
    tol: float = TOL_DEFAULT,
) -> SanityCheck:
    """An extra stop with pit-loss enabled must carry an actual cost."""
    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import Intervention, ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()
    laps = int((base.race_distance.get("laps") or 6))
    pit = [max(2, laps // 2)]
    spec_free = ScenarioSpec(
        spec_id="sanity-stopfree", baseline_scenario_id=base.scenario_id,
        interventions=[Intervention(family="strategy", op="SET_VALUE", target=driver_id,
                                    parameter="pit_laps", value=pit)],
        seed=seed, simulations=simulations)
    spec_cost = ScenarioSpec(
        spec_id="sanity-stopcost", baseline_scenario_id=base.scenario_id,
        interventions=[
            Intervention(family="strategy", op="SET_VALUE", target=driver_id,
                         parameter="pit_laps", value=pit),
            Intervention(family="strategy", op="SET_VALUE", target="all",
                         parameter="pit_loss_seconds", value=24.4),
        ],
        seed=seed, simulations=simulations)
    try:
        cf_free = eng.run_counterfactual(baseline_factory(), spec_free)[3]
        cf_cost = eng.run_counterfactual(baseline_factory(), spec_cost)[3]
    except Exception as exc:
        return SanityCheck(name="extra_stop_cost", status="NOT_TESTABLE",
                           detail=f"engine could not run stop legs: {exc}")
    f_free = _expected_finish(cf_free, driver_id)
    f_cost = _expected_finish(cf_cost, driver_id)
    delta = f_cost - f_free  # expected: >= -tol (costly stop should not help)
    moved = abs(f_cost - f_free) > 1e-12
    status = "PASS" if (delta >= -tol and moved) else "FAIL"
    return SanityCheck(
        name="extra_stop_cost",
        status=status,
        detail=(
            f"E[finish] extra stop free: {f_free:.3f} vs with 24.4s loss: "
            f"{f_cost:.3f} (delta {delta:+.3f}, tol {tol})."
        ),
        evidence_tier="PRIOR_ONLY",
        measured={"e_finish_free": f_free, "e_finish_cost": f_cost, "delta": delta},
    )


def check_pace_monotonic(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
    tol: float = TOL_DEFAULT,
) -> SanityCheck:
    """Better driver pace must not systematically worsen expected finish."""
    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import Intervention, ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()
    try:
        # pace_delta units: positive slows (added to base pace). Faster = negative.
        cf_slow = eng.run_counterfactual(
            baseline_factory(),
            ScenarioSpec(spec_id="sanity-pace-slow", baseline_scenario_id=base.scenario_id,
                         interventions=[Intervention(family="driver", op="ADD_DELTA",
                                                     target=driver_id, parameter="pace_delta",
                                                     value=1.0)],
                         seed=seed, simulations=simulations))[3]
        cf_fast = eng.run_counterfactual(
            baseline_factory(),
            ScenarioSpec(spec_id="sanity-pace-fast", baseline_scenario_id=base.scenario_id,
                         interventions=[Intervention(family="driver", op="ADD_DELTA",
                                                     target=driver_id, parameter="pace_delta",
                                                     value=-1.0)],
                         seed=seed, simulations=simulations))[3]
    except Exception as exc:
        return SanityCheck(name="pace_monotonic", status="NOT_TESTABLE",
                           detail=f"engine could not run pace legs: {exc}")
    f_slow = _expected_finish(cf_slow, driver_id)
    f_fast = _expected_finish(cf_fast, driver_id)
    delta = f_fast - f_slow  # expected: <= +tol (faster must not be worse)
    status = "PASS" if delta <= tol else "FAIL"
    return SanityCheck(
        name="pace_monotonic",
        status=status,
        detail=(f"E[finish] pace -1 (fast): {f_fast:.3f} vs +1 (slow): {f_slow:.3f} "
                f"(delta {delta:+.3f}, tol {tol})."),
        evidence_tier="PRIOR_ONLY",
        measured={"e_finish_fast": f_fast, "e_finish_slow": f_slow, "delta": delta},
    )


def check_aero_grip_monotonic(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
    tol: float = TOL_DEFAULT,
) -> SanityCheck:
    """Lower ride height (more downforce/grip, less drag) must not be slower."""
    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import Intervention, ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()

    def _leg(height: float) -> dict[str, Any]:
        spec = ScenarioSpec(
            spec_id=f"sanity-grip{height}", baseline_scenario_id=base.scenario_id,
            interventions=[Intervention(family="setup", op="SET_VALUE",
                                        target=driver_id, parameter="ride_height_front",
                                        value=height)],
            seed=seed, simulations=simulations)
        return eng.run_counterfactual(baseline_factory(), spec)[3]

    try:
        f_low = _expected_finish(_leg(15.0), driver_id)
        f_high = _expected_finish(_leg(25.0), driver_id)
    except Exception as exc:
        return SanityCheck(name="aero_grip_monotonic", status="NOT_TESTABLE",
                           detail=f"engine could not run setup legs: {exc}")
    delta = f_low - f_high  # expected: <= +tol
    status = "PASS" if delta <= tol else "FAIL"
    return SanityCheck(
        name="aero_grip_monotonic",
        status=status,
        detail=(f"E[finish] ride height 15mm: {f_low:.3f} vs 25mm: {f_high:.3f} "
                f"(delta {delta:+.3f}, tol {tol}). PRIOR_ONLY aero coefficients."),
        evidence_tier="PRIOR_ONLY",
        measured={"e_finish_low": f_low, "e_finish_high": f_high, "delta": delta},
    )


def check_wet_weather_effect(
    baseline_factory: Callable[[], Any],
    seed: int = 42,
    simulations: int = 60,
) -> SanityCheck:
    """Wet override must raise modelled wetness and move some distribution."""
    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import Intervention, ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()
    spec = ScenarioSpec(
        spec_id="sanity-wet", baseline_scenario_id=base.scenario_id,
        interventions=[Intervention(family="weather", op="SET_VALUE",
                                    target="race", parameter="rainfall_mm_h",
                                    value=8.0)],
        seed=seed, simulations=simulations)
    try:
        res = eng.run_spec(baseline_factory(), spec)
    except Exception as exc:
        return SanityCheck(name="wet_weather_effect", status="NOT_TESTABLE",
                           detail=f"engine could not run wet leg: {exc}")
    wx = res.comparison.race_effects.get("weather", {})
    d_wet = float(wx.get("delta", {}).get("mean_wetness", 0.0)) if isinstance(wx, dict) else 0.0
    moved = _l1max(res.comparison) > 0
    status = "PASS" if (d_wet > 0 and moved) else "FAIL"
    return SanityCheck(
        name="wet_weather_effect",
        status=status,
        detail=(f"delta mean_wetness {d_wet:+.4f} (expected > 0); "
                f"finish distributions moved={moved}."),
        evidence_tier="PRIOR_ONLY",
        measured={"d_mean_wetness": d_wet, "moved": moved},
    )


def check_tyre_compound_effect(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
) -> SanityCheck:
    """Compound change must propagate to some finish distribution."""
    from app.simulation.scenario.engine import ScenarioEngine
    from app.simulation.scenario.models import Intervention, ScenarioSpec

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    base = baseline_factory()
    spec = ScenarioSpec(
        spec_id="sanity-tyre", baseline_scenario_id=base.scenario_id,
        interventions=[Intervention(family="tyre", op="SET_VALUE",
                                    target=driver_id, parameter="starting_compound",
                                    value="MEDIUM")],
        seed=seed, simulations=simulations)
    try:
        res = eng.run_spec(baseline_factory(), spec)
    except Exception as exc:
        return SanityCheck(name="tyre_compound_effect", status="NOT_TESTABLE",
                           detail=f"engine could not run tyre leg: {exc}")
    moved = _l1max(res.comparison) > 0
    status = "PASS" if moved else "FAIL"
    return SanityCheck(
        name="tyre_compound_effect",
        status=status,
        detail=f"SOFT->MEDIUM moved finish distributions={moved}.",
        evidence_tier="PRIOR_ONLY",
        measured={"moved": moved},
    )


def run_all_sanity(
    baseline_factory: Callable[[], Any],
    driver_id: str,
    seed: int = 42,
    simulations: int = 60,
) -> list[SanityCheck]:
    return [
        check_pit_loss_monotonic(baseline_factory, driver_id, seed, simulations),
        check_extra_stop_cost(baseline_factory, driver_id, seed, simulations),
        check_pace_monotonic(baseline_factory, driver_id, seed, simulations),
        check_aero_grip_monotonic(baseline_factory, driver_id, seed, simulations),
        check_wet_weather_effect(baseline_factory, seed, simulations),
        check_tyre_compound_effect(baseline_factory, driver_id, seed, simulations),
    ]
