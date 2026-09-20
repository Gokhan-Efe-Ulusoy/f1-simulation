"""Walk-forward and model comparison — Phase 27."""

from __future__ import annotations

import statistics
from typing import List, Dict


def walk_forward_validation(
    records,
    splits: List[tuple],
    decomposition_factory,
) -> List[dict]:
    """Chronological walk-forward.

    splits: list of (train_end_season, val_seasons)
    decomposition_factory: callable returning new LapTimeDecomposition
    """
    results = []
    for train_end, val_seasons in splits:
        train = [r for r in records if r.season <= train_end]
        val = [r for r in records if r.season in val_seasons]
        if not train or not val:
            # need at least 500 laps each?
            results.append({"train": f"<={train_end}", "val": val_seasons, "status": "NOT_TESTABLE"})  # noqa: E501
            continue
        model = decomposition_factory()
        model.fit(train)
        # baseline: circuit mean only
        baseline_mae = _mae(train, val, model, baseline_only=True)
        candidate_mae = _mae(train, val, model, baseline_only=False)
        improvement = baseline_mae - candidate_mae if baseline_mae and candidate_mae else None
        results.append({
            "train": f"<={train_end}",
            "val": val_seasons,
            "n_train": len(train),
            "n_val": len(val),
            "baseline_lap_MAE": baseline_mae,
            "candidate_lap_MAE": candidate_mae,
            "improvement": improvement,
            "status": "ok" if improvement is not None else "NOT_TESTABLE",
        })
    return results


def _mae(train, val, model, baseline_only: bool) -> float | None:
    if not val:
        return None
    errors = []
    for rec in val:
        if not rec.lap_time_seconds or not (50 < rec.lap_time_seconds < 400):
            continue
        pred = model.predict(rec)
        if baseline_only:
            # only circuit baseline
            est = pred.circuit_baseline
        else:
            est = pred.total_predicted
        errors.append(abs(est - rec.lap_time_seconds))
    return statistics.mean(errors) if errors else None


def compare_models(records, model_configs: Dict[str, callable]) -> Dict[str, dict]:
    """Compare multiple model specs on same split."""
    # Use train <=2023 val 2024 as representative, plus walk-forward already
    train = [r for r in records if r.season <= 2023]
    val = [r for r in records if r.season == 2024]
    results = {}
    for name, factory in model_configs.items():
        model = factory()
        if train:
            model.fit(train)
        # compute train and validation MAE
        train_mae = _mae(train, train, model, baseline_only=False) if train else None
        val_mae = _mae(train, val, model, baseline_only=False) if val else None
        results[name] = {
            "train_MAE": train_mae,
            "validation_MAE": val_mae,
            "evidence_tier": "LIMITED",
        }
    return results
