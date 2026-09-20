"""FastF1 modern session-data adapter architecture (Phase 9B).

FastF1 is an optional dependency (not in base requirements). When
installed, this adapter exposes sessions/laps/sectors/telemetry/tyre/
weather/position surfaces; otherwise every fetch raises DataUnavailable
instead of fabricating data. No network calls happen at import time.
"""
from __future__ import annotations

from typing import Any

from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter


def fastf1_available() -> bool:
    """True only when the fastf1 package is importable (no import side effects)."""
    import importlib.util

    return importlib.util.find_spec("fastf1") is not None


class FastF1Adapter(SourceAdapter):
    """Adapter shell for FastF1 session data (modern eras only)."""

    provider = "fastf1"

    def _require(self) -> Any:
        if not fastf1_available():
            raise DataUnavailable(
                "fastf1 is not installed; modern session data unavailable")
        import importlib

        return importlib.import_module("fastf1")

    def fetch_season(self, season: int) -> RawBundle:
        """Season schedule is out of scope for FastF1; use Jolpica/CSV."""
        raise DataUnavailable("fastf1 adapter is session-scoped, not season-scoped")

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        """Not implemented without an event schedule mapping; see fetch_session."""
        raise DataUnavailable(
            "use fetch_session(season, event, session_name) for FastF1 data")

    def fetch_session(
        self, season: int, event: str | int, session_name: str
    ) -> RawBundle:
        """Describe one session load (actual download happens in run_ingestion)."""
        self._require()
        return RawBundle(
            provider=self.provider,
            endpoint=f"{season}/{event}/{session_name}",
            records=[{
                "season": season, "event": event, "session_name": session_name,
                "note": "payload materialized by run_ingestion, not at import",
            }],
        )

    def is_available(self) -> bool:
        """Report backend availability without side effects."""
        return fastf1_available()
