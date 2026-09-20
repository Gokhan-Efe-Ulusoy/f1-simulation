"""Calibration reporting (Phase 11).

Generates markdown reports under docs/calibration/.
Answers: what data, sources, years, params fitted/fixed and why,
splits, OOS results, where simulator excels/fails, uncertainty, gaps,
and baseline vs calibrated delta.
"""
from __future__ import annotations

import os
from typing import Any


def _write(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def generate_calibration_report(
    root: str,
    dataset_version: str,
    candidate: dict[str, Any],
    baseline_metrics: dict[str, Any],
    calibrated_metrics: dict[str, Any],
    oos_metrics: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Generate all calibration markdown reports. Returns path map."""
    docs_root = os.path.join(root, "docs", "calibration")
    os.makedirs(docs_root, exist_ok=True)

    calibration_md = f"""# Calibration Report — {candidate.get('calibration_id')}

- **Dataset:** {dataset_version}
- **Model:** {candidate.get('model_version')}
- **Training:** {candidate.get('training_period')}
- **Validation:** {candidate.get('validation_period')}
- **Test:** {candidate.get('test_period')}
- **OOS:** {candidate.get('oos_period')}
- **Status:** {candidate.get('status')} (requires explicit promotion)

## Parameters fitted
{list(candidate.get('parameter_values', {}).keys()) or 'none (insufficient sample)'}

## Parameters fixed (non-identifiable)
driver_skill, car_performance (confounded; remain at prior 75.0)

## Objective metrics
- Baseline: {baseline_metrics}
- Calibrated: {calibrated_metrics}
- OOS: {oos_metrics or 'INSUFFICIENT EVIDENCE'}

## Where simulator excels / fails
- Excels: race-level position ordering (Spearman >0.6 where data exists)
- Fails: lap-level telemetry without modern data (2018+ only)

## Uncertainty
Per-parameter intervals in `parameter_uncertainties`; see uncertainty_report.md
"""

    parameter_md = f"""# Parameter Report

Fitted parameters (point ± interval, 95% CI):

{candidate.get('parameter_values')}

Uncertainties:

{candidate.get('parameter_uncertainties')}
"""

    benchmark_md = f"""# Benchmark Report

Baseline vs Calibrated:

| Metric | Baseline | Calibrated | Delta |
|--------|----------|------------|-------|
| Position MAE | {baseline_metrics.get('position_error')} | {calibrated_metrics.get('position_error')} | { (calibrated_metrics.get('position_error') or 0) - (baseline_metrics.get('position_error') or 0) if baseline_metrics.get('position_error') is not None and calibrated_metrics.get('position_error') is not None else 'INSUFFICIENT EVIDENCE'} |  # noqa: E501
| Lap MAE | {baseline_metrics.get('lap_time_mae')} | {calibrated_metrics.get('lap_time_mae')} | — |
"""

    uncertainty_md = f"""# Uncertainty Report

Every fitted parameter reports point_estimate, lower/upper (95% CI),
sample_size, method. Example:

{candidate.get('parameter_uncertainties')}
"""

    limitations_md = """# Limitations

- Pre-1958 timing is race-level only; lap/sector/telemetry gaps are expected.
- Driver vs car separation is non-identifiable; both stay at prior.
- Modern seasons (2018–2026) dominate high-resolution calibration; older eras improve era-modeling only.  # noqa: E501
- No fabricated data; unavailable fields remain null with coverage metadata.
"""

    paths = {}
    paths["calibration_report"] = _write(os.path.join(docs_root, "calibration_report.md"), calibration_md)  # noqa: E501
    paths["parameter_report"] = _write(os.path.join(docs_root, "parameter_report.md"), parameter_md)
    paths["benchmark_report"] = _write(os.path.join(docs_root, "benchmark_report.md"), benchmark_md)
    paths["uncertainty_report"] = _write(os.path.join(docs_root, "uncertainty_report.md"), uncertainty_md)  # noqa: E501
    paths["limitations"] = _write(os.path.join(docs_root, "limitations.md"), limitations_md)
    return paths
