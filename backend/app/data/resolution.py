"""Entity resolution: names/aliases -> stable canonical IDs (Phase 9C).

Entities (drivers, constructors, circuits) are resolved through alias
registries. Events (races) are never merged by venue: the same circuit
hosting a different Grand Prix is a different race_id.
"""
from __future__ import annotations

import re
import unicodedata

# Sponsor/legal suffixes stripped for matching only (canonical names kept).
_SUFFIX_PATTERNS = (
    r"\bf1 team\b", r"\bformula 1\b", r"\bformula one\b", r"\bgrand prix\b",
    r"\bgp\b", r"\bracing\b", r"\bmotorsport\b", r"\binternational\b",
)


def normalize_name(name: str) -> str:
    """Normalize a name for matching: accents/case/punctuation-insensitive."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    for pattern in _SUFFIX_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class AliasRegistry:
    """Bidirectional alias store: normalized alias -> canonical ID."""

    def __init__(self) -> None:
        self._aliases: dict[str, str] = {}
        self._entities: dict[str, set[str]] = {}

    def register_entity(self, canonical_id: str, names: list[str]) -> None:
        """Register one entity with all its known name variants."""
        known = self._entities.setdefault(canonical_id, set())
        for name in names:
            key = normalize_name(name)
            if not key:
                continue
            owner = self._aliases.get(key)
            if owner is not None and owner != canonical_id:
                raise ValueError(
                    f"alias conflict: {name!r} already maps to {owner!r}")
            self._aliases[key] = canonical_id
            known.add(name)

    def resolve(self, name: str) -> str | None:
        """Return the canonical ID for a name variant, or None if unknown."""
        return self._aliases.get(normalize_name(name))

    def canonical_ids(self) -> list[str]:
        """All registered canonical IDs, sorted for determinism."""
        return sorted(self._entities)

    def aliases_for(self, canonical_id: str) -> list[str]:
        """Known name variants for one entity, sorted for determinism."""
        return sorted(self._entities.get(canonical_id, set()))


def make_race_id(season: int, event_slug: str) -> str:
    """Build a race event ID (event slug, never the circuit ID)."""
    slug = re.sub(r"[^a-z0-9]+", "-", event_slug.strip().lower()).strip("-")
    return f"{season}-{slug}"


def make_result_id(race_id: str, driver_id: str) -> str:
    """Build a deterministic classification-entry ID."""
    return f"{race_id}:{driver_id}"
