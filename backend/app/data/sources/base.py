"""Source adapter contract (Phase 9B).

Adapters never normalize across providers; they emit source-specific raw
records plus the provenance facts needed downstream. HTTP is injectable so
tests never touch the network.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawBundle:
    """One fetch unit: raw records with source context."""

    provider: str
    endpoint: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Transport: (url) -> parsed JSON-compatible payload. Default uses urllib.
Transport = Callable[[str], Any]


class SourceAdapter(ABC):
    """Common adapter interface; subsets may raise DataUnavailable."""

    provider: str = "base"

    @abstractmethod
    def fetch_season(self, season: int) -> RawBundle:
        """Fetch season-level raw records."""

    @abstractmethod
    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        """Fetch one race event including results."""

    def fetch_driver(self, driver_ref: str) -> RawBundle:
        """Fetch one driver record (optional for most adapters)."""
        raise DataUnavailable(f"{self.provider}: driver fetch not supported")

    def fetch_constructor(self, constructor_ref: str) -> RawBundle:
        """Fetch one constructor record (optional for most adapters)."""
        raise DataUnavailable(f"{self.provider}: constructor fetch not supported")

    def fetch_results(self, season: int, round_number: int) -> RawBundle:
        """Fetch classification rows (defaults to fetch_race)."""
        return self.fetch_race(season, round_number)


class DataUnavailable(RuntimeError):
    """Raised when a source cannot provide requested data (never fabricated)."""
