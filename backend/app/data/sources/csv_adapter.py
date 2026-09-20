"""Local CSV adapter for public historical archives (Phase 9B).

Expected files (all optional; headers validated, unknown columns kept):
- drivers.csv: driver_ref,full_name,nationality,date_of_birth
- constructors.csv: constructor_ref,name,nationality
- races.csv: season,round,race_name,circuit_ref,date,scheduled_laps
- results.csv: season,round,driver_ref,constructor_ref,grid,position,status,
  laps,time_gap_points...
The adapter never invents missing columns; absent data stays absent.
"""
from __future__ import annotations

import csv
import os
from typing import Any

from app.data.sources.base import RawBundle, SourceAdapter

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "drivers": ("driver_ref",),
    "constructors": ("constructor_ref",),
    "races": ("season", "round"),
    "results": ("season", "round", "driver_ref"),
}


class OfficialCsvAdapter(SourceAdapter):
    """Adapter reading a directory of CSV extracts."""

    provider = "official_csv"

    def __init__(self, directory: str):
        self._directory = directory

    def _read(self, name: str) -> RawBundle:
        path = os.path.join(self._directory, f"{name}.csv")
        if not os.path.exists(path):
            return RawBundle(provider=self.provider, endpoint=path,
                             rejected=[f"missing file: {name}.csv"])
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS[name] if c not in (reader.fieldnames or [])]
            if missing:
                return RawBundle(provider=self.provider, endpoint=path,
                                 rejected=[f"{name}.csv missing columns: {missing}"])
            records: list[dict[str, Any]] = []
            rejected: list[str] = []
            for lineno, row in enumerate(reader, start=2):
                if not any((v or "").strip() for v in row.values()):
                    continue  # skip blank lines, counted as neither
                if not row.get(REQUIRED_COLUMNS[name][0], "").strip():
                    rejected.append(f"{name}.csv:{lineno}: empty key")
                    continue
                records.append(dict(row))
        return RawBundle(provider=self.provider, endpoint=path,
                         records=records, rejected=rejected)

    def fetch_season(self, season: int) -> RawBundle:
        """All schedule rows for one season (filtered post-read)."""
        bundle = self._read("races")
        bundle.records = [r for r in bundle.records if str(r.get("season")) == str(season)]
        return bundle

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        """Classification rows for one round."""
        bundle = self._read("results")
        bundle.records = [r for r in bundle.records
                          if str(r.get("season")) == str(season)
                          and str(r.get("round")) == str(round_number)]
        return bundle

    def fetch_driver(self, driver_ref: str) -> RawBundle:
        """Driver rows matching a reference."""
        bundle = self._read("drivers")
        bundle.records = [r for r in bundle.records if r.get("driver_ref") == driver_ref]
        return bundle

    def fetch_constructor(self, constructor_ref: str) -> RawBundle:
        """Constructor rows matching a reference."""
        bundle = self._read("constructors")
        bundle.records = [r for r in bundle.records
                          if r.get("constructor_ref") == constructor_ref]
        return bundle
