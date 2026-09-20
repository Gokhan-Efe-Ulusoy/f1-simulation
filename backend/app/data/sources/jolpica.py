"""Jolpica (Ergast-compatible) historical API adapter (Phase 9B).

Free public API, no key required. Only JSON GETs for:
seasons, season schedule, round results, qualifying, driver/constructor
standings. Network access is injectable; offline use must go through
stored raw bundles instead.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from app.data.sources.base import RawBundle, SourceAdapter, Transport

BASE_URL = "https://api.jolpi.ca/ergast/f1"


def _urllib_transport(url: str, timeout_seconds: float = 30.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


class JolpicaAdapter(SourceAdapter):
    """Adapter for the Jolpica Ergast-compatible API."""

    provider = "jolpica"

    def __init__(self, transport: Transport | None = None, base_url: str = BASE_URL):
        self._transport = transport or _urllib_transport
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        return self._transport(f"{self._base_url}/{path.lstrip('/')}")

    def fetch_season(self, season: int) -> RawBundle:
        """Fetch the season schedule (one record per round)."""
        payload = self._get(f"{season}.json")
        try:
            races = payload["MRData"]["RaceTable"]["Races"]
        except (KeyError, TypeError) as exc:
            return RawBundle(provider=self.provider, endpoint=f"{season}.json",
                             rejected=[f"unexpected schedule shape: {exc}"])
        records = [dict(race, _season=season) for race in races]
        return RawBundle(provider=self.provider, endpoint=f"{season}.json", records=records)

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        """Fetch one round including classification rows."""
        payload = self._get(f"{season}/{round_number}/results.json")
        try:
            races = payload["MRData"]["RaceTable"]["Races"]
            race = races[0]
            rows = race.get("Results", [])
        except (KeyError, TypeError, IndexError) as exc:
            return RawBundle(
                provider=self.provider, endpoint=f"{season}/{round_number}/results.json",
                rejected=[f"unexpected results shape: {exc}"])
        records = [dict(row, _season=season, _round=round_number,
                        _race_name=race.get("raceName", ""),
                        _circuit_id=race.get("Circuit", {}).get("circuitId", ""),
                        _date=race.get("date", "")) for row in rows]
        return RawBundle(
            provider=self.provider, endpoint=f"{season}/{round_number}/results.json",
            records=records)

    def fetch_driver(self, driver_ref: str) -> RawBundle:
        """Fetch one driver profile."""
        payload = self._get(f"drivers/{driver_ref}.json")
        try:
            drivers = payload["MRData"]["DriverTable"]["Drivers"]
        except (KeyError, TypeError) as exc:
            return RawBundle(provider=self.provider, endpoint=f"drivers/{driver_ref}.json",
                             rejected=[f"unexpected driver shape: {exc}"])
        return RawBundle(provider=self.provider, endpoint=f"drivers/{driver_ref}.json",
                         records=list(drivers))

    def fetch_constructor(self, constructor_ref: str) -> RawBundle:
        """Fetch one constructor profile."""
        payload = self._get(f"constructors/{constructor_ref}.json")
        try:
            constructors = payload["MRData"]["ConstructorTable"]["Constructors"]
        except (KeyError, TypeError) as exc:
            return RawBundle(
                provider=self.provider, endpoint=f"constructors/{constructor_ref}.json",
                rejected=[f"unexpected constructor shape: {exc}"])
        return RawBundle(provider=self.provider, endpoint=f"constructors/{constructor_ref}.json",
                         records=list(constructors))
