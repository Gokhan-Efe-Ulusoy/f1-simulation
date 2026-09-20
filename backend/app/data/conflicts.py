"""Cross-source conflict detection and resolution (Phase 9C).

Conflicting facts are recorded, never silently picked. Resolution uses an
explicit, configurable source-priority list and always states its reason.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_SOURCE_PRIORITY: list[str] = ["official_f1", "fia", "jolpica", "fastf1",
                                      "weather", "external"]


class DataConflict(BaseModel):
    """One field-level disagreement between sources."""

    entity_id: str
    field: str
    values: dict[str, str] = Field(default_factory=dict)  # provider -> value
    resolution: str = ""  # chosen value ("" = unresolved)
    resolution_reason: str = ""

    model_config = {"use_enum_values": True}


def compare_fact(
    entity_id: str,
    field: str,
    provider_values: dict[str, str],
    priority: list[str] | None = None,
) -> DataConflict | None:
    """Compare one fact across providers; None when all agree (or empty)."""
    distinct = set(provider_values.values())
    if len(distinct) <= 1:
        return None
    order = priority or DEFAULT_SOURCE_PRIORITY
    ranked = sorted(provider_values, key=lambda p: order.index(p) if p in order else len(order))
    winner = ranked[0]
    return DataConflict(
        entity_id=entity_id,
        field=field,
        values=dict(sorted(provider_values.items())),
        resolution=provider_values[winner],
        resolution_reason=f"source priority: {winner} first in {order}",
    )


def detect_conflicts(
    facts: list[tuple[str, str, dict[str, str]]],
    priority: list[str] | None = None,
) -> list[DataConflict]:
    """Detect conflicts over many (entity, field, provider->value) facts."""
    found: list[DataConflict] = []
    for entity_id, field, values in facts:
        conflict = compare_fact(entity_id, field, values, priority)
        if conflict is not None:
            found.append(conflict)
    return sorted(found, key=lambda c: (c.entity_id, c.field))
