"""Temporal train/validation/test splits (Phase 9E).

Time-aware only: seasons split by year boundaries, never by random
sampling. Defaults follow the platform convention.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SplitName = Literal["train", "validation", "test", "out_of_sample"]


class TemporalSplit(BaseModel):
    """Year-boundary split configuration."""

    train_end: int = Field(default=2000, ge=1950, le=2026)
    validation_end: int = Field(default=2010, ge=1950, le=2026)
    test_end: int = Field(default=2020, ge=1950, le=2026)

    model_config = {"use_enum_values": True}

    def assign(self, season: int) -> SplitName:
        """Assign one season year to a split."""
        if season <= self.train_end:
            return "train"
        if season <= self.validation_end:
            return "validation"
        if season <= self.test_end:
            return "test"
        return "out_of_sample"

    def describe(self) -> dict[str, tuple[int, int]]:
        """Human-readable year ranges per split."""
        return {
            "train": (1950, self.train_end),
            "validation": (self.train_end + 1, self.validation_end),
            "test": (self.validation_end + 1, self.test_end),
            "out_of_sample": (self.test_end + 1, 2026),
        }
