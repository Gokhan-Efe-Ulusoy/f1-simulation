"""Phase 22 — Intervention attribution.

Answers what changed / where / what downstream variables changed / what
final metrics changed — citing only pathways the engines actually implement
(Phase 21 PATHWAYS registry) and effects actually measured in the comparison.
Language is model-attributed, never real-world causal.
"""
from __future__ import annotations

from typing import Any

from app.simulation.replay.models import (
    AttributionLevel,
    ExtendedComparison,
    InterventionAttribution,
)


def build_attribution(
    experiment_id: str,
    trace: list[Any],
    comparison: ExtendedComparison,
) -> InterventionAttribution:
    try:
        from app.simulation.scenario.registry import PATHWAYS
    except Exception:
        PATHWAYS = {}

    what: list[str] = []
    where: list[str] = []
    fams: list[str] = []
    for t in trace:
        fam = getattr(t, "family", "?")
        param = getattr(t, "parameter", "?")
        target = getattr(t, "target", "?")
        b = getattr(t, "baseline_value", None)
        c = getattr(t, "counterfactual_value", None)
        what.append(f"{fam}.{param}: {b} -> {c}")
        where.append(f"target {target} via {getattr(t, 'modifier_path', '')}")
        if fam not in fams:
            fams.append(str(fam))

    downstream_set: list[str] = []
    for fam in fams:
        for step in PATHWAYS.get(fam, [])[1:-1]:
            if step not in downstream_set:
                downstream_set.append(step)

    ranked = sorted(
        comparison.driver_deltas,
        key=lambda e: abs(e.d_win_probability),
        reverse=True,
    )
    final: list[str] = []
    for e in ranked[:3]:
        rel = f"{e.relative_win_delta:+.3f}" if e.relative_win_delta is not None else "n/a"
        final.append(
            f"{e.driver_id}: model-attributed dP(win)={e.d_win_probability:+.4f} "
            f"(relative {rel}; base {e.baseline_win_probability:.4f} -> cf "
            f"{e.counterfactual_win_probability:.4f}), dE[finish]={e.d_expected_finish:+.3f}, "
            f"dP(DNF)={e.d_dnf_probability:+.4f}, dP(top10)={e.d_top10_probability:+.4f}"
        )
    if not ranked:
        final.append("no drivers compared (empty result)")

    tiers = set(comparison.evidence_tiers.values()) or {"PRIOR_ONLY"}
    tier = sorted(tiers)[0] if len(tiers) == 1 else "PRIOR_ONLY"
    return InterventionAttribution(
        experiment_id=experiment_id,
        intervention="; ".join(what) or "no interventions (baseline preservation probe)",
        what_changed=what or ["no interventions (baseline preservation probe)"],
        where_changed=where,
        downstream=AttributionLevel(
            direct=[f"{fam}: {PATHWAYS.get(fam, ['(unmapped)'])[0]}" for fam in fams],
            downstream=downstream_set,
            final=final,
        ),
        evidence_tier=tier,
    )
