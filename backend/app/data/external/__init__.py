"""Phase 22.5 external-data acquisition pipeline.

Reproducible discovery -> download -> audit -> normalize -> stage flow for
legally accessible third-party F1 datasets. Raw payloads are immutable;
all interpretation happens downstream. No network access at import time.
"""

from app.data.external.base import (  # noqa: F401  (re-exported)
    EVIDENCE_TIERS,
    EVIDENCE_TIER_ORDER,
    QUALITY_CRITERIA,
    EvidenceTier,
    SourceDescriptor,
    SourceQuality,
)

EXTERNAL_PIPELINE_VERSION = "1.0.0"
