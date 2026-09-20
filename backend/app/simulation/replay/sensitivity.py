"""Phase 22 — Sensitivity engine (one-factor-at-a-time + bounded grids).

Sweeps one intervention parameter over a deterministic value grid while every
other model component stays identical (shared baseline leg, common random
numbers). Bounded by construction: OFAT costs len(values) legs; grids are
capped at MAX_GRID_CELLS. Never builds (N,D,L,candidates,interventions)
tensors — each leg is an independent (N,D) simulation.
"""
from __future__ import annotations

from typing import Any

from app.simulation.replay.models import SensitivityPoint, SensitivityResult

MAX_GRID_POINTS = 25


class SensitivityEngine:
    """Deterministic sensitivity sweeps over the scenario engine."""

    def __init__(self, seed: int = 42, simulations: int = 60):
        self.seed = seed
        self.simulations = simulations

    def _engine(self):  # lazy import (avoids cycles at module load)
        from app.simulation.scenario.engine import ScenarioEngine

        return ScenarioEngine(seed=self.seed, simulations=self.simulations)

    def run_ofat(
        self,
        baseline: Any,
        experiment_id: str,
        family: str,
        target: str,
        parameter: str,
        values: list[Any],
        op: str = "SET_VALUE",
        seed: int | None = None,
        simulations: int | None = None,
        reason: str = "",
    ) -> SensitivityResult:
        """One-factor-at-a-time sweep over `values` (deterministic order)."""
        from app.simulation.scenario.models import Intervention, ScenarioSpec

        if len(values) > MAX_GRID_POINTS:
            raise ValueError(
                f"OFAT grid of {len(values)} exceeds cap {MAX_GRID_POINTS} "
                f"(refine the range instead)"
            )
        seed = self.seed if seed is None else int(seed)
        simulations = self.simulations if simulations is None else int(simulations)
        eng = self._engine()
        branches = {
            f"v{i}": [Intervention(
                intervention_id=f"{experiment_id}-s{i}",
                family=family,  # type: ignore[arg-type]
                op=op,  # type: ignore[arg-type]
                target=target,
                parameter=parameter,
                value=value,
                reason=reason or f"OFAT {parameter}={value}",
            )]
            for i, value in enumerate(values)
        }
        out = eng.run_branch(
            baseline, branches, seed=seed, simulations=simulations,
            spec_id_prefix=experiment_id,
        )
        names = list(branches.keys())
        b_fp = out[names[0]].baseline_fingerprint if names else ""
        points: list[SensitivityPoint] = []
        for (name, value) in zip(names, values):
            res = out[name]
            top = sorted(
                res.comparison.driver_effects,
                key=lambda e: abs(e.d_win_probability),
                reverse=True,
            )
            e0 = top[0] if top else None
            l1max = max((e.l1_finish_distribution for e in res.comparison.driver_effects), default=0.0)  # noqa: E501
            points.append(SensitivityPoint(
                parameter=parameter,
                value=value,
                target=target,
                d_win_probability=float(e0.d_win_probability) if e0 else 0.0,
                d_expected_finish=float(e0.d_expected_finish) if e0 else 0.0,
                l1_finish_distribution=float(l1max),
                uncertainty_note=(
                    f"N={simulations}, seed={seed}, CRN; granularity "
                    f"~{1.0 / max(1, simulations):.4f} per probability point."
                ),
                evidence_tier=(res.comparison.evidence_tiers.get(family, "PRIOR_ONLY")),
            ))
        return SensitivityResult(
            experiment_id=experiment_id,
            method="one_factor_at_a_time",
            family=family,
            parameter=parameter,
            target=target,
            points=points,
            baseline_fingerprint=b_fp,
            seed=seed,
            simulations=simulations,
            evidence_tier="PRIOR_ONLY",
            limitations=[
                "OFAT varies one parameter; interactions are not estimated.",
                "Magnitudes are model-implied under PRIOR_ONLY coefficients.",
                f"Grid capped at {MAX_GRID_POINTS} points to bound compute.",
            ],
        )

    def run_grid(
        self,
        baseline: Any,
        experiment_id: str,
        axes: dict[str, list[Any]],
        family: str,
        target: str,
        op: str = "SET_VALUE",
        seed: int | None = None,
        simulations: int | None = None,
    ) -> SensitivityResult:
        """Bounded 2-axis grid (product capped at MAX_GRID_POINTS)."""
        import itertools

        from app.simulation.scenario.models import Intervention

        if len(axes) != 2:
            raise ValueError("run_grid supports exactly 2 axes (bounded by design)")
        names = list(axes.keys())
        combos = list(itertools.product(*[axes[k] for k in names]))
        if len(combos) > MAX_GRID_POINTS:
            raise ValueError(
                f"grid of {len(combos)} exceeds cap {MAX_GRID_POINTS}"
            )
        seed = self.seed if seed is None else int(seed)
        simulations = self.simulations if simulations is None else int(simulations)
        eng = self._engine()
        branches = {
            f"g{i}": [
                Intervention(
                    intervention_id=f"{experiment_id}-g{i}-{p}",
                    family=family,  # type: ignore[arg-type]
                    op=op,  # type: ignore[arg-type]
                    target=target,
                    parameter=p,
                    value=v,
                )
                for p, v in zip(names, combo)
            ]
            for i, combo in enumerate(combos)
        }
        out = eng.run_branch(
            baseline, branches, seed=seed, simulations=simulations,
            spec_id_prefix=experiment_id,
        )
        keys = list(branches.keys())
        b_fp = out[keys[0]].baseline_fingerprint if keys else ""
        points: list[SensitivityPoint] = []
        for key, combo in zip(keys, combos):
            res = out[key]
            top = sorted(
                res.comparison.driver_effects,
                key=lambda e: abs(e.d_win_probability),
                reverse=True,
            )
            e0 = top[0] if top else None
            l1max = max((e.l1_finish_distribution for e in res.comparison.driver_effects), default=0.0)  # noqa: E501
            points.append(SensitivityPoint(
                parameter="+".join(names),
                value=dict(zip(names, combo)),
                target=target,
                d_win_probability=float(e0.d_win_probability) if e0 else 0.0,
                d_expected_finish=float(e0.d_expected_finish) if e0 else 0.0,
                l1_finish_distribution=float(l1max),
                uncertainty_note=f"N={simulations}, seed={seed}, CRN.",
                evidence_tier="PRIOR_ONLY",
            ))
        return SensitivityResult(
            experiment_id=experiment_id,
            method="bounded_grid_2d",
            family=family,
            parameter="+".join(names),
            target=target,
            points=points,
            baseline_fingerprint=b_fp,
            seed=seed,
            simulations=simulations,
            evidence_tier="PRIOR_ONLY",
            limitations=[
                "Bounded 2-axis grid; higher-order interactions not estimated.",
                f"Grid capped at {MAX_GRID_POINTS} cells.",
            ],
        )
