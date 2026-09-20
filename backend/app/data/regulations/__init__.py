"""Regulation layers (Phase 9D curated knowledge + Phase 22.5 evidence schema).

`curated` carries the pre-existing high-confidence facts (provider tag
"curated", never mistaken for observations). `schema` defines the Phase 22.5
regulation *evidence* layer: season regulation states with sources and
confidence — evidence only, no simulation coefficients.
"""
from app.data.regulations.curated import (  # noqa: F401
    curated_provider_tag,
    regulations_for_season,
)
from app.data.regulations.schema import (  # noqa: F401
    REGULATION_CATEGORIES,
    RegulationParameter,
    load_evidence,
)
