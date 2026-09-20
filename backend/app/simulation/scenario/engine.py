"""Phase 21 — ScenarioEngine: baseline / counterfactual execution + comparison.

Pipeline: baseline Scenario -> real engine -> baseline distribution;
interventions -> compiled counterfactual Scenario -> SAME engine, SAME seed
(common random numbers) -> counterfactual distribution; then structured
comparison + model-implied explanation.

The caller's baseline object is never mutated (deep copies at every step).
No output deltas are fabricated: every effect emerges from the engines.
"""
from __future__ import annotations

from typing import Any

from app.simulation.scenario.models import (
    InterventionTrace,
    ScenarioComparison,
    ScenarioExplanation,
    ScenarioResult,
    ScenarioSpec,
)
from app.simulation.scenario.compiler import (
    baseline_fingerprint,
    build_branch_specs,
    compile_spec,
    spec_fingerprint,
    scenario_content_hash,
)
from app.simulation.scenario.comparison import compare_results
from app.simulation.scenario.registry import FAMILY_TIERS, PATHWAYS
from app.simulation.scenario.validation import check_spec


def _scenario_engine():
    from app.simulation.race_engine_v21 import ScenarioAwareRaceEngine

    return ScenarioAwareRaceEngine


class ScenarioEngine:
    """Counterfactual & scenario orchestration over the existing engines."""

    def __init__(self, seed: int = 42, simulations: int = 100):
        self.default_seed = seed
        self.default_simulations = simulations

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _simulate(self, scenario: Any, simulations: int, seed: int) -> dict[str, Any]:
        eng_cls = _scenario_engine()
        eng = eng_cls(seed=seed)
        # Deep copy: engines may annotate hypothetical_modifiers in place.
        snapshot = scenario.model_copy(deep=True)
        return eng.simulate(snapshot, simulations=simulations, seed=seed)

    def run_baseline(
        self, baseline: Any, simulations: int | None = None, seed: int | None = None
    ) -> dict[str, Any]:
        return self._simulate(
            baseline,
            simulations if simulations is not None else self.default_simulations,
            seed if seed is not None else self.default_seed,
        )

    def run_counterfactual(
        self, baseline: Any, spec: ScenarioSpec
    ) -> tuple[Any, list[InterventionTrace], list[str], dict[str, Any]]:
        """Compile + run one counterfactual leg. Returns
        (compiled_scenario, trace, warnings, result)."""
        compiled, trace, warnings = compile_spec(baseline, spec)
        result = self._simulate(compiled, spec.simulations, spec.seed)
        return compiled, trace, warnings, result

    def run_spec(self, baseline: Any, spec: ScenarioSpec) -> ScenarioResult:
        """Full pipeline for one spec: both legs (CRN) + comparison + explanation."""
        b_fp = baseline_fingerprint(baseline)
        c_fp = spec_fingerprint(spec, scenario_content_hash(baseline))
        baseline_result = self._simulate(baseline, spec.simulations, spec.seed)
        compiled, trace, warnings, cf_result = self.run_counterfactual(baseline, spec)
        tiers = {t.family: t.evidence_tier for t in trace}
        comparison = compare_results(
            spec.spec_id, baseline_result, cf_result,
            baseline_fp=b_fp, counterfactual_fp=c_fp,
            seed=spec.seed, simulations=spec.simulations, evidence_tiers=tiers,
        )
        explanation = build_explanation(spec, trace, comparison, warnings)
        return ScenarioResult(
            spec_id=spec.spec_id,
            scenario_type=str(spec.scenario_type),
            baseline_fingerprint=b_fp,
            counterfactual_fingerprint=c_fp,
            seed=spec.seed,
            simulations=spec.simulations,
            trace=trace,
            comparison=comparison,
            explanation=explanation,
            provenance={
                "baseline_scenario_id": spec.baseline_scenario_id,
                "scenario_type": str(spec.scenario_type),
                "warnings": warnings,
                "versions": _engine_versions(),
            },
        )

    def run_branch(
        self, baseline: Any, branches: dict[str, list], **kwargs: Any
    ) -> dict[str, ScenarioResult]:
        """Baseline leg runs ONCE; every branch shares its seed (CRN)."""
        seed = int(kwargs.get("seed", self.default_seed))
        simulations = int(kwargs.get("simulations", self.default_simulations))
        scenario_type = str(kwargs.get("scenario_type", "counterfactual"))
        prefix = str(kwargs.get("spec_id_prefix", getattr(baseline, "scenario_id", "branch")))
        specs = build_branch_specs(
            getattr(baseline, "scenario_id", "baseline"),
            prefix, branches, scenario_type, seed, simulations,
        )
        b_fp = baseline_fingerprint(baseline)
        baseline_result = self._simulate(baseline, simulations, seed)
        out: dict[str, ScenarioResult] = {}
        for name, spec in zip(branches.keys(), specs):
            c_fp = spec_fingerprint(spec, scenario_content_hash(baseline))
            compiled, trace, warnings, cf_result = self.run_counterfactual(baseline, spec)
            tiers = {t.family: t.evidence_tier for t in trace}
            comparison = compare_results(
                spec.spec_id, baseline_result, cf_result,
                baseline_fp=b_fp, counterfactual_fp=c_fp,
                seed=seed, simulations=simulations, evidence_tiers=tiers,
            )
            out[name] = ScenarioResult(
                spec_id=spec.spec_id,
                scenario_type=scenario_type,
                baseline_fingerprint=b_fp,
                counterfactual_fingerprint=c_fp,
                seed=seed,
                simulations=simulations,
                trace=trace,
                comparison=comparison,
                explanation=build_explanation(spec, trace, comparison, warnings),
                provenance={
                    "baseline_scenario_id": spec.baseline_scenario_id,
                    "scenario_type": scenario_type,
                    "warnings": warnings,
                    "versions": _engine_versions(),
                },
            )
        return out


def _engine_versions() -> dict[str, str]:
    try:
        from app.simulation import version as V

        return {
            k: str(getattr(V, k, ""))
            for k in (
                "MODEL_VERSION", "SIMULATION_VERSION", "RACEENGINE_VERSION",
                "SCENARIO_MODEL_VERSION", "STRATEGY_MODEL_VERSION",
                "WEATHER_MODEL_VERSION", "RACE_CONTROL_MODEL_VERSION",
                "SETUP_MODEL_VERSION", "DATASET_VERSION", "CALIBRATION_VERSION",
            )
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Explanation (generated only from trace + comparison + declared pathways)
# ---------------------------------------------------------------------------

def build_explanation(
    spec: ScenarioSpec,
    trace: list[InterventionTrace],
    comparison: ScenarioComparison,
    warnings: list[str] | None = None,
) -> ScenarioExplanation:
    what = [t_description(t) for t in trace] or ["no interventions (baseline preservation probe)"]
    fams = sorted({t.family for t in trace})
    why: list[str] = []
    pathways: dict[str, list[str]] = {}
    for fam in fams:
        chain = PATHWAYS.get(fam, [])
        pathways[fam] = list(chain)
        if chain:
            why.append(f"{fam}: {' -> '.join(chain)}")

    ranked = sorted(
        comparison.driver_effects,
        key=lambda e: abs(e.d_win_probability),
        reverse=True,
    )
    how: list[str] = []
    for e in ranked[:3]:
        how.append(
            f"{e.driver_id}: dP(win)={e.d_win_probability:+.4f} "
            f"(base {e.baseline_win_probability:.4f} -> cf {e.counterfactual_win_probability:.4f}), "  # noqa: E501
            f"dE[finish]={e.d_expected_finish:+.3f}, dP(DNF)={e.d_dnf_probability:+.4f}"
        )
    if not ranked:
        how.append("no drivers compared (empty result)")

    unc = [
        f"N={comparison.simulations}, seed={comparison.seed}, common random numbers across legs.",
        f"Monte Carlo granularity ~{1.0 / max(1, comparison.simulations):.4f} per probability point; "  # noqa: E501
        "treat sub-granularity deltas as noise.",
        "Effect evidence: " + (
            ", ".join(f"{k}={v}" for k, v in sorted(comparison.evidence_tiers.items()))
            or "none (empty spec)"
        ) + ". Monte Carlo output never upgrades these tiers.",
    ]
    asm = [
        "Baseline setup is the neutral Phase 20 baseline (historical setups unknown).",
        "Pit stops carry no time loss in the vectorized model; added stops show "
        "tyre-freshness benefit only.",
        "Tyre compound effects use calibrated betas where available, priors otherwise.",
        "Setup coefficients are prior-only; magnitudes are order-of-magnitude.",
    ]
    for w in warnings or []:
        asm.append(f"compile warning: {w}")
    if any(t.family in ("strategy", "tyre") for t in trace):
        asm.append(
            "Strategy/tyre schedule interventions propagate through the pit-age / "
            "degradation channel only (no DecisionEngine policy change in vectorized runs)."
        )
    return ScenarioExplanation(
        spec_id=spec.spec_id,
        what_changed=what,
        why_changed=why,
        how_much=how,
        uncertainty=unc,
        assumptions=asm,
        pathways=pathways,
    )


def t_description(t: InterventionTrace) -> str:
    try:
        return t.describe()
    except Exception:
        return f"{t.family}.{t.parameter} [{t.target}] {t.op}"
