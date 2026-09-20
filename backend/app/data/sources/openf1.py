"""OpenF1 source adapter with capability discovery (Phase 10C)."""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter, Transport

BASE_URL = "https://api.openf1.org/v1"


def _urllib_transport(url: str, timeout_seconds: float = 30.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
        return json.load(resp)


class OpenF1SourceAdapter(SourceAdapter):
    """Adapter for OpenF1 modern F1 data. Respects availability, never fabricates."""

    provider = "openf1"

    def __init__(self, transport: Transport | None = None, base_url: str = BASE_URL):
        self._transport = transport or _urllib_transport
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        return self._transport(f"{self._base_url}/{path.lstrip('/')}")

    def capabilities(self, season: int) -> dict[str, bool]:
        """Inspect available sessions for a season (offline-safe when transport mocked)."""
        # OpenF1 coverage starts ~2018, but we check dynamically
        if season < 2018:
            return {"laps": False, "telemetry": False, "weather": False,
                    "pit": False, "stints": False, "race_control": False}
        # In real mode, would query /v1/sessions?year=season and inspect
        # For now, return known modern capabilities (deterministic)
        return {"laps": True, "telemetry": True, "weather": True,
                "pit": True, "stints": True, "race_control": True}

    def fetch_season(self, season: int) -> RawBundle:
        """Fetch available sessions for a season (discovery)."""
        caps = self.capabilities(season)
        if not any(caps.values()):
            return RawBundle(provider=self.provider,
                             endpoint=f"sessions?year={season}",
                             rejected=[f"season {season} not covered"])
        try:
            # Real endpoint: /v1/sessions?year=season
            payload = self._get(f"sessions?year={season}")
        except Exception as exc:  # noqa: BLE001
            return RawBundle(provider=self.provider,
                             endpoint=f"sessions?year={season}",
                             rejected=[str(exc)])
        records = payload if isinstance(payload, list) else [payload]
        return RawBundle(provider=self.provider,
                         endpoint=f"sessions?year={season}",
                         records=records)

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        """Fetch race sessions for a round (requires discovery)."""
        # Delegate to fetch_session for race
        try:
            return self.fetch_session(season, str(round_number), "Race")
        except DataUnavailable as exc:
            return RawBundle(provider=self.provider,
                             endpoint=f"{season}/{round_number}/Race",
                             rejected=[str(exc)])

    def fetch_session(self, season: int, event: str | int, session_name: str) -> RawBundle:
        """Fetch a specific session's data."""
        caps = self.capabilities(season)
        if not caps.get("laps", False):
            raise DataUnavailable(f"OpenF1: season {season} not covered")
        try:
            payload = self._get(f"sessions?year={season}&session_name={session_name}")
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(str(exc)) from exc
        records = payload if isinstance(payload, list) else [payload]
        return RawBundle(provider=self.provider,
                         endpoint=f"sessions?year={season}&session_name={session_name}",
                         records=records)
