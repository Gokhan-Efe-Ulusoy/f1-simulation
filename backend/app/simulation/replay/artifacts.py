"""Phase 22 — Reproducible experiment artifacts (machine + human readable).

Machine artifact: backend/data/simulation/experiments/experiment-<race>-<slug>-<hash>.json
  (full CounterfactualExperiment + provenance + fingerprint; reproducible
  from its own metadata).
Human report: backend/docs/experiments/<name>.md distinguishing OBSERVED /
  MODEL INPUT / MODEL ASSUMPTION / SIMULATED / NON_IDENTIFIABLE.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.simulation.replay.models import CounterfactualExperiment


def experiments_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in [Path.cwd(), here, *here.parents]:
        cand2 = parent / "data" / "simulation" / "experiments"
        if (parent / "data" / "canonical" / "races.json").exists():
            cand2.mkdir(parents=True, exist_ok=True)
            return cand2
        cand = parent / "backend" / "data" / "simulation" / "experiments"
        if (parent / "backend" / "data" / "canonical" / "races.json").exists():
            cand.mkdir(parents=True, exist_ok=True)
            return cand
    out = Path.cwd() / "experiments"
    out.mkdir(parents=True, exist_ok=True)
    return out


def reports_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in [Path.cwd(), here, *here.parents]:
        cand2 = parent / "docs" / "experiments"
        if (parent / "docs").exists() and (parent / "data" / "canonical" / "races.json").exists():
            cand2.mkdir(parents=True, exist_ok=True)
            return cand2
        cand = parent / "backend" / "docs" / "experiments"
        if (parent / "backend" / "docs").exists():
            cand.mkdir(parents=True, exist_ok=True)
            return cand
    out = Path.cwd() / "experiment_reports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return slug[:48] or "experiment"


def save_experiment(exp: CounterfactualExperiment, slug: str = "") -> Path:
    """Persist the artifact; filename carries race + slug + fingerprint."""
    payload = exp.model_dump()
    payload["artifact_kind"] = "phase22_counterfactual_experiment"
    payload["artifact_version"] = "1.0.0"
    slug = slugify(slug or exp.experiment_id)
    path = experiments_dir() / f"experiment-{exp.race_id}-{slug}-{exp.fingerprint}.json"
    path.write_text(json.dumps(payload, indent=1, default=str))
    return path


def load_experiment(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def experiment_reproducible_from_artifact(path: str | Path) -> bool:
    """Check the artifact contains everything needed to re-run it."""
    art = load_experiment(path)
    required = ("race_id", "spec", "seed", "simulations", "laps",
                "fingerprint", "provenance")
    if any(k not in art or art[k] in (None, "") for k in required):
        return False
    prov = art.get("provenance", {})
    if not prov.get("versions"):
        return False
    spec = art.get("spec", {})
    if not spec.get("interventions") and "pit" not in json.dumps(spec):
        # Empty-intervention probes are valid; anything else needs the list.
        if spec.get("interventions") is None:
            return False
    return True


def render_markdown_report(exp: CounterfactualExperiment) -> str:
    """Human-readable report with explicit OBSERVED/ASSUMED/SIMULATED labels."""
    comp = exp.comparison
    lines: list[str] = [
        f"# Experiment: {exp.experiment_id}",
        "",
        "## Question",
        "",
        exp.question or "(no question recorded)",
        "",
        "## Historical context (OBSERVED)",
        "",
        f"- Race: {exp.race_id} (OBSERVED identity from canonical dataset)",
        f"- Race date / as_of: {exp.provenance.get('race_date', '')} / {exp.provenance.get('as_of', '')}",  # noqa: E501
        f"- Observed result is a post-hoc validation target only (OBSERVED, never a model input).",
        "",
        "## Available evidence",
        "",
    ]
    for key, tier in sorted((exp.evidence or {}).items()):
        lines.append(f"- {key}: {tier}")
    if not exp.evidence:
        lines.append("- (no family evidence recorded)")
    lines += [
        "",
        "## Baseline (SIMULATED from MODEL INPUT)",
        "",
        f"- Fingerprint: `{exp.baseline_fingerprint}`",
        f"- N={exp.simulations}, seed={exp.seed}, laps={exp.laps}",
        "",
        "## Counterfactual (SIMULATED from MODEL INPUT + INTERVENTION)",
        "",
        f"- Fingerprint: `{exp.counterfactual_fingerprint}`",
        "",
        "## Intervention (MODEL INPUT)",
        "",
    ]
    for t in exp.trace:
        lines.append(
            f"- {t.get('family')}.{t.get('parameter')} [{t.get('target')}] "
            f"{t.get('op')}: {t.get('baseline_value')} -> {t.get('counterfactual_value')} "
            f"({t.get('evidence_tier')})"
        )
    if not exp.trace:
        lines.append("- (none: baseline preservation probe)")
    lines += [
        "",
        "## Assumptions (MODEL ASSUMPTION)",
        "",
    ]
    for lim in exp.limitations:
        lines.append(f"- {lim}")
    lines += [
        "",
        "## Simulation configuration",
        "",
        f"- CRN: baseline_seed={exp.crn_manifest.baseline_seed if exp.crn_manifest else exp.seed}, "
        f"counterfactual_seed={exp.crn_manifest.counterfactual_seed if exp.crn_manifest else exp.seed}, "  # noqa: E501
        f"same_seed={exp.crn_manifest.same_seed if exp.crn_manifest else True}",
        "- Streams: same seed / sim index / isolated exogenous streams (see stream manifest in artifact).",  # noqa: E501
        "",
        "## Results (SIMULATED)",
        "",
    ]
    if comp is not None:
        ranked = sorted(comp.driver_deltas, key=lambda e: abs(e.d_win_probability), reverse=True)[:8]  # noqa: E501
        lines.append("| driver | dP(win) | dP(podium) | dP(top10) | dE[finish] | dP(DNF) | L1 |")
        lines.append("|---|---|---|---|---|---|---|")
        for e in ranked:
            lines.append(
                f"| {e.driver_id} | {e.d_win_probability:+.4f} | "
                f"{e.d_podium_probability:+.4f} | {e.d_top10_probability:+.4f} | "
                f"{e.d_expected_finish:+.3f} | {e.d_dnf_probability:+.4f} | {e.l1_finish_distribution:.4f} |"  # noqa: E501
            )
        lines += ["", "### Distribution comparison notes", ""]
        lines += [f"- {n}" for n in comp.metric_notes]
        lines += ["", "### Unmeasurable (honestly qualified)", ""]
        for key, tier in sorted(comp.unmeasurable.items()):
            lines.append(f"- {key}: {tier}")
    else:
        lines.append("- (no comparison recorded)")
    lines += [
        "",
        "## Attribution (MODEL-ATTRIBUTED, not causal)",
        "",
    ]
    if exp.attribution is not None:
        lines.append(f"- Intervention: {exp.attribution.intervention}")
        lines.append("- Direct: " + "; ".join(exp.attribution.downstream.direct))
        lines.append("- Downstream: " + "; ".join(exp.attribution.downstream.downstream))
        lines.append("- Final: " + "; ".join(exp.attribution.downstream.final))
        lines.append(f"- {exp.attribution.disclaimer}")
    lines += [
        "",
        "## Sensitivity",
        "",
    ]
    if exp.sensitivity is not None:
        s = exp.sensitivity
        lines.append(f"- Method: {s.method} over {s.parameter} ({len(s.points)} points).")
        for p in s.points:
            lines.append(
                f"  - {p.parameter}={p.value}: dP(win)={p.d_win_probability:+.4f}, "
                f"dE[finish]={p.d_expected_finish:+.3f}, L1={p.l1_finish_distribution:.4f}"
            )
    else:
        lines.append("- (no sensitivity sweep attached)")
    lines += [
        "",
        "## Uncertainty",
        "",
        f"- Monte Carlo granularity ~{1.0 / max(1, exp.simulations):.4f} per probability point; "
        "treat sub-granularity deltas as noise.",
        "- No p-values or significance claims (no justified test implemented).",
        "",
        "## Limitations",
        "",
    ]
    for lim in exp.limitations:
        lines.append(f"- {lim}")
    lines += [
        "- NON_IDENTIFIABLE quantities (historical weather/setup/fuel/strategy/tyre) "
        "were never substituted with fabricated values.",
        "",
        "## Reproducibility",
        "",
        f"- Experiment fingerprint: `{exp.fingerprint}`",
        f"- Artifact: `backend/data/simulation/experiments/experiment-{exp.race_id}-*-{exp.fingerprint}.json`",  # noqa: E501
        "- Re-run from artifact metadata: same race_id + spec + seed + N + versions.",
        "",
    ]
    versions = exp.provenance.get("versions", {}) if isinstance(exp.provenance, dict) else {}
    if versions:
        lines.append("### Versions")
        lines.append("")
        for key in sorted(versions):
            lines.append(f"- {key}: {versions[key]}")
        lines.append("")
    return "\n".join(lines)


def save_markdown_report(exp: CounterfactualExperiment, name: str = "") -> Path:
    path = reports_dir() / f"{slugify(name or exp.experiment_id)}.md"
    path.write_text(render_markdown_report(exp))
    return path
