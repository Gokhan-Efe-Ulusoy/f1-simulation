"""Temporal cross-validation (Phase 11).

Never randomly mixes future into training. Supports both default
1950–2000/2001–2010/2011–2020/2021–2026 and era-aware splits.
"""
from __future__ import annotations

from app.data.splits import TemporalSplit


def temporal_folds(
    split: TemporalSplit | None = None,
) -> dict[str, tuple[int, int]]:
    """Return year ranges per split (train/validation/test/oos)."""
    split = split or TemporalSplit()
    return split.describe()


def is_temporal_leak(train_years: list[int], test_years: list[int]) -> bool:
    """True if any test year <= max train year (temporal leak)."""
    if not train_years or not test_years:
        return False
    return max(test_years) <= max(train_years) or min(test_years) <= max(train_years)


def era_aware_split(era_boundaries: list[int], train_eras: list[int]) -> dict[str, list[int]]:
    """Split by era indices (e.g. train first N eras)."""
    # Simplified: return train vs rest
    all_eras = list(range(len(era_boundaries)))
    train = [e for e in all_eras if e in train_eras]
    test = [e for e in all_eras if e not in train]
    return {"train": train, "test": test}
