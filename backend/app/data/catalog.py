"""Source catalog and reliability tiers (Phase 10A).

Provides SourceCatalog with rich metadata, tier definitions, and
field-level source priority. Used by ingestion, fusion and validation.
No network access at import time.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReliabilityTier(str, Enum):
    """Source reliability hierarchy (TIER 1 = most authoritative)."""

    TIER_1 = "tier_1_official"
    TIER_2 = "tier_2_structured_api"
    TIER_3 = "tier_3_curated_research"
    TIER_4 = "tier_4_community"


class SourceType(str, Enum):
    """Kind of source technology."""

    API = "api"
    ARCHIVE = "archive"
    DATASET = "dataset"
    DOCUMENT = "document"
    SCRAPED = "scraped"


class SourceMetadata(BaseModel):
    """One entry in the SourceCatalog."""

    source_id: str = Field(description="Stable identifier, e.g. 'jolpica'")
    provider: str = Field(description="Organization/provider name")
    source_type: SourceType = SourceType.API
    description: str = ""
    homepage: str = ""
    api_url: str = Field(default="", description="API/documentation URL")
    coverage_start: int = Field(default=1950, ge=1950, le=2026)
    coverage_end: int = Field(default=2026, ge=1950, le=2026)
    supported_entities: list[str] = Field(
        default_factory=list,
        description="e.g. ['season','race','driver','constructor','result']",
    )
    supported_resolution: list[str] = Field(
        default_factory=list,
        description="e.g. ['race','lap','sector','telemetry']",
    )
    license: str = Field(default="unknown", description="SPDX or free text")
    terms_notes: str = Field(default="", description="Usage constraints, rate limits")
    retrieval_method: str = Field(default="https GET JSON",
                                  description="How data is retrieved")
    reliability_tier: ReliabilityTier = ReliabilityTier.TIER_3
    active: bool = True
    last_verified: str = Field(default="", description="ISO date of last check")

    model_config = {"use_enum_values": True}


class FieldSourcePriority(BaseModel):
    """Field-level source priority (first = highest)."""

    field: str
    priority: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


DEFAULT_FIELD_PRIORITIES: list[FieldSourcePriority] = [
    FieldSourcePriority(field="race_winner", priority=["official_f1", "fia", "jolpica", "openf1", "kaggle", "github"]),  # noqa: E501
    FieldSourcePriority(field="grid_position", priority=["official_f1", "fia", "jolpica", "kaggle", "github"]),  # noqa: E501
    FieldSourcePriority(field="lap_time", priority=["official_f1", "openf1", "fastf1", "kaggle", "jolpica"]),  # noqa: E501
    FieldSourcePriority(field="telemetry", priority=["fastf1", "openf1"]),
    FieldSourcePriority(field="tyre_stint", priority=["fastf1", "openf1", "kaggle"]),
    FieldSourcePriority(field="weather", priority=["fastf1", "openf1", "weather_api"]),
    FieldSourcePriority(field="pit_stop", priority=["official_f1", "openf1", "fastf1", "kaggle"]),
]

# Pre-populated catalog entries (extensible via add_source)
DEFAULT_SOURCES: list[SourceMetadata] = [
    SourceMetadata(
        source_id="jolpica",
        provider="Jolpica (Ergast-compatible)",
        source_type=SourceType.API,
        description="Historical F1 results, qualifying, standings via Ergast-compatible API",
        homepage="https://github.com/jolpica/jolpica-f1",
        api_url="https://api.jolpi.ca/ergast/f1",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["season", "race", "circuit", "driver", "constructor", "result", "qualifying", "standing"],  # noqa: E501
        supported_resolution=["race"],
        license="CC BY-SA (Ergast heritage) / provider terms",
        terms_notes="Free public API, respect rate limits, no key required",
        retrieval_method="https GET JSON with pagination",
        reliability_tier=ReliabilityTier.TIER_2,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="openf1",
        provider="OpenF1",
        source_type=SourceType.API,
        description="Modern F1 live timing and session data",
        homepage="https://www.openf1.org",
        api_url="https://api.openf1.org/v1",
        coverage_start=2018,
        coverage_end=2026,
        supported_entities=["session", "driver", "lap", "stint", "position", "weather", "telemetry"],  # noqa: E501
        supported_resolution=["lap", "telemetry"],
        license="OpenF1 terms",
        terms_notes="Respect rate limits, dynamic session discovery",
        retrieval_method="https GET JSON per session",
        reliability_tier=ReliabilityTier.TIER_2,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="fastf1",
        provider="FastF1",
        source_type=SourceType.API,
        description="Modern detailed timing and telemetry via FastF1 library",
        homepage="https://github.com/theOehrly/Fast-F1",
        api_url="https://github.com/theOehrly/Fast-F1",
        coverage_start=2018,
        coverage_end=2026,
        supported_entities=["session", "lap", "sector", "telemetry", "tyre", "weather", "position"],
        supported_resolution=["sector", "telemetry"],
        license="MIT",
        retrieval_method="Python library with cache",
        reliability_tier=ReliabilityTier.TIER_2,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="kaggle_generic",
        provider="Kaggle (generic)",
        source_type=SourceType.DATASET,
        description="Curated research datasets (owner/slug, versioned)",
        homepage="https://www.kaggle.com/datasets",
        api_url="https://www.kaggle.com/api/v1",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["race", "driver", "constructor", "result"],
        supported_resolution=["race", "lap"],
        license="Dataset-specific",
        terms_notes="Respect dataset license, record owner/slug/version/hash",
        retrieval_method="Kaggle API or manual download + local import",
        reliability_tier=ReliabilityTier.TIER_3,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="github_generic",
        provider="GitHub (generic)",
        source_type=SourceType.ARCHIVE,
        description="Repository datasets (CSV/JSON/Parquet/releases)",
        homepage="https://github.com",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["race", "driver", "constructor", "result"],
        supported_resolution=["race"],
        license="Repository-specific",
        terms_notes="Pin to commit SHA or immutable release, sanitize paths",
        retrieval_method="raw content via commit SHA or release asset",
        reliability_tier=ReliabilityTier.TIER_3,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="official_f1",
        provider="Formula 1 Official",
        source_type=SourceType.DOCUMENT,
        description="Official Formula 1 historical information",
        homepage="https://www.formula1.com",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["race", "driver", "constructor", "circuit"],
        supported_resolution=["race"],
        license="All rights reserved, fair use for research",
        terms_notes="Check terms before redistribution",
        retrieval_method="Curated import of official timing documents",
        reliability_tier=ReliabilityTier.TIER_1,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="fia_documents",
        provider="FIA",
        source_type=SourceType.DOCUMENT,
        description="FIA sporting and technical regulations, official classifications",
        homepage="https://www.fia.com",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["regulation", "race", "standing"],
        supported_resolution=["race"],
        license="FIA terms",
        terms_notes="Official documents, curated extraction",
        reliability_tier=ReliabilityTier.TIER_1,
        active=True,
        last_verified="2026-01-15",
    ),
    SourceMetadata(
        source_id="weather_api",
        provider="Weather provider (generic)",
        source_type=SourceType.API,
        description="Historical weather observations",
        homepage="",
        coverage_start=1950,
        coverage_end=2026,
        supported_entities=["weather"],
        supported_resolution=["race"],
        license="Provider-specific",
        terms_notes="Verify licensing before production use",
        retrieval_method="API or local import",
        reliability_tier=ReliabilityTier.TIER_2,
        active=True,
        last_verified="2026-01-15",
    ),
]


class SourceCatalog(BaseModel):
    """Registry of known sources with priority resolution."""

    sources: list[SourceMetadata] = Field(default_factory=list)
    field_priorities: list[FieldSourcePriority] = Field(
        default_factory=lambda: [p.model_copy() for p in DEFAULT_FIELD_PRIORITIES]
    )

    model_config = {"use_enum_values": True}

    def add_source(self, meta: SourceMetadata) -> None:
        """Add a source; duplicates by source_id are rejected."""
        if any(s.source_id == meta.source_id for s in self.sources):
            raise ValueError(f"duplicate source_id: {meta.source_id}")
        self.sources.append(meta)

    def get(self, source_id: str) -> SourceMetadata | None:
        """Lookup by source_id."""
        for src in self.sources:
            if src.source_id == source_id:
                return src
        return None

    def active_sources(self) -> list[SourceMetadata]:
        """Only active entries, sorted by tier then provider."""
        tier_order = {
            ReliabilityTier.TIER_1: 0,
            ReliabilityTier.TIER_2: 1,
            ReliabilityTier.TIER_3: 2,
            ReliabilityTier.TIER_4: 3,
        }
        return sorted(
            [s for s in self.sources if s.active],
            key=lambda s: (tier_order.get(s.reliability_tier, 99), s.provider),
        )

    def priority_for_field(self, field: str) -> list[str]:
        """Ordered provider list for a field (fallback to tier order)."""
        for entry in self.field_priorities:
            if entry.field == field:
                return list(entry.priority)
        # Fallback: tier order
        return [s.source_id for s in self.active_sources()]

    def set_priority(self, field: str, priority: list[str]) -> None:
        """Configure field-level priority (overwrites or creates)."""
        for entry in self.field_priorities:
            if entry.field == field:
                entry.priority = list(priority)
                return
        self.field_priorities.append(FieldSourcePriority(field=field, priority=list(priority)))

    def to_dict(self) -> dict[str, Any]:
        """Serializable snapshot."""
        return self.model_dump()


def default_catalog() -> SourceCatalog:
    """Pre-populated catalog with all default sources."""
    return SourceCatalog(sources=[s.model_copy() for s in DEFAULT_SOURCES])
