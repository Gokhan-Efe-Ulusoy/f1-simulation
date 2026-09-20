"""License/access gate (Phase 22.5).

A source may only be *acquired* when its license is known and permits local
research ingestion. Reference-only sources (official F1/FIA) are documented
but never downloaded. Kaggle mirrors require per-dataset verification.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseGate:
    """Acquisition policy for one source."""

    source_id: str
    may_download: bool
    reason: str
    attribution_required: bool = False


_LICENSE_GATES: dict[str, LicenseGate] = {
    "jolpica-laps": LicenseGate("jolpica-laps", True, "Free public API", False),
    "jolpica-pitstops": LicenseGate("jolpica-pitstops", True, "Free public API", False),
    "jolpica-results": LicenseGate("jolpica-results", True, "Free public API (already ingested)", False),  # noqa: E501
    "openf1-timing": LicenseGate("openf1-timing", True, "Historical free, no key", False),
    "openf1-stints": LicenseGate("openf1-stints", True, "Historical free, no key", False),
    "openf1-weather": LicenseGate("openf1-weather", True, "Historical free, no key", False),
    "openf1-racecontrol": LicenseGate("openf1-racecontrol", True, "Historical free, no key", False),
    "openf1-pit": LicenseGate("openf1-pit", True, "Historical free, no key", False),
    "openf1-telemetry": LicenseGate("openf1-telemetry", True, "Historical free; sample-only policy", False),  # noqa: E501
    "fastf1-timing": LicenseGate("fastf1-timing", True, "MIT library + local cache", False),
    "f1db-database": LicenseGate("f1db-database", True, "CC BY 4.0, pinned tag", True),
    "openmeteo-era5": LicenseGate("openmeteo-era5", True, "CC BY 4.0, free archive API", True),
    "ergast-mirror-kaggle": LicenseGate(
        "ergast-mirror-kaggle", False,
        "Per-dataset license unverified + auth required; document only", False),
    "fia-documents": LicenseGate(
        "fia-documents", False,
        "No open endpoint; curated evidence layer only, no redistribution", False),
    "official-f1-timing": LicenseGate(
        "official-f1-timing", False,
        "All rights reserved; reference cross-checks only, no scraping", False),
}


def gate_for(source_id: str) -> LicenseGate:
    """Return the license gate (unknown sources default to deny)."""
    return _LICENSE_GATES.get(
        source_id,
        LicenseGate(source_id, False, "Unknown source: deny by default", False),
    )


def may_acquire(source_id: str) -> bool:
    """True when a source may be downloaded/stored locally."""
    return gate_for(source_id).may_download
