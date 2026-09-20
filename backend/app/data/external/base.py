"""Core contracts for Phase 22.5 external-data acquisition.

Evidence tiers reuse the project-wide vocabulary (NEVER fabricate: a
variable that cannot be observed keeps its honest tier). Source quality is
recorded as objective boolean criteria, never a subjective score.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceTier(str, Enum):
    """Variable-level evidence status. Ordered weakest -> strongest."""

    NOT_AVAILABLE = "NOT_AVAILABLE"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    PRIOR_ONLY = "PRIOR_ONLY"
    LIMITED = "LIMITED"
    PARTIAL = "PARTIAL"
    FULL = "FULL"
    CALIBRATED = "CALIBRATED"


EVIDENCE_TIER_ORDER: dict[str, int] = {t.value: i for i, t in enumerate(EvidenceTier)}

EVIDENCE_TIERS: list[str] = [t.value for t in EvidenceTier]

#: Objective source-quality criteria (all booleans, no subjective scoring).
QUALITY_CRITERIA: list[str] = [
    "provenance_known",
    "license_known",
    "schema_documented",
    "raw_data_available",
    "timestamp_available",
    "historical_coverage",
    "granularity_lap_or_better",
    "independent_verification",
]


class SourceQuality(BaseModel):
    """Objective quality flags for one source (no aggregate score)."""

    provenance_known: bool = False
    license_known: bool = False
    schema_documented: bool = False
    raw_data_available: bool = False
    timestamp_available: bool = False
    historical_coverage: bool = False
    granularity_lap_or_better: bool = False
    independent_verification: bool = False

    model_config = {"use_enum_values": True}

    def satisfied(self) -> list[str]:
        """Names of criteria that hold."""
        return [c for c in QUALITY_CRITERIA if bool(getattr(self, c, False))]

    def missing(self) -> list[str]:
        """Names of criteria that do not hold."""
        return [c for c in QUALITY_CRITERIA if not bool(getattr(self, c, False))]


class SourceClass(str, Enum):
    """Source provenance class (transparent quality system)."""

    OFFICIAL = "OFFICIAL"
    VERIFIED_RESEARCH = "VERIFIED_RESEARCH"
    PRIMARY_OPEN_DATA = "PRIMARY_OPEN_DATA"
    REPUTABLE_SECONDARY = "REPUTABLE_SECONDARY"
    COMMUNITY_DATA = "COMMUNITY_DATA"
    UNVERIFIED = "UNVERIFIED"


class SourceDescriptor(BaseModel):
    """One candidate external source with full provenance metadata."""

    source_id: str = Field(description="Stable id, e.g. 'jolpica-laps'")
    source_name: str = ""
    url: str = ""
    provider: str = ""
    license: str = "unknown"
    access_method: str = ""
    years: str = ""
    races: str = ""
    sessions: str = ""
    variables: list[str] = Field(default_factory=list)
    granularity: str = ""
    format: str = ""
    provenance: str = ""
    update_frequency: str = ""
    known_limitations: str = ""
    terms_of_use: str = ""
    evidence_tier: str = EvidenceTier.LIMITED.value
    source_class: str = SourceClass.COMMUNITY_DATA.value
    quality: SourceQuality = Field(default_factory=SourceQuality)
    acquisition_status: str = Field(
        default="DOCUMENTED",
        description="DOCUMENTED | ACQUIRED | REJECTED | BLOCKED",
    )
    acquisition_note: str = ""

    model_config = {"use_enum_values": True}

    def to_dict(self) -> dict[str, Any]:
        """Serializable snapshot."""
        return self.model_dump()
