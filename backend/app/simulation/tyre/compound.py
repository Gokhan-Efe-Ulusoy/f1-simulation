"""Compound normalization — canonical taxonomy, preserves provenance."""
from __future__ import annotations

from enum import Enum

class CanonicalCompound(str, Enum):
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"
    UNKNOWN = "UNKNOWN"

# Source -> canonical mapping, only where scientifically justified
COMPOUND_ALIASES: dict[str, CanonicalCompound] = {
    "SOFT": CanonicalCompound.SOFT,
    "SOFT TYRE": CanonicalCompound.SOFT,
    "C5": CanonicalCompound.SOFT,
    "C4": CanonicalCompound.SOFT,
    "C3": CanonicalCompound.MEDIUM,
    "C2": CanonicalCompound.HARD,
    "C1": CanonicalCompound.HARD,
    "MEDIUM": CanonicalCompound.MEDIUM,
    "HARD": CanonicalCompound.HARD,
    "INTERMEDIATE": CanonicalCompound.INTERMEDIATE,
    "INTER": CanonicalCompound.INTERMEDIATE,
    "WET": CanonicalCompound.WET,
    "FULL WET": CanonicalCompound.WET,
}

def normalize_compound(source_compound: str | None) -> tuple[CanonicalCompound | None, str | None]:
    """Returns (canonical, source) or (None, source) if unknown."""
    if source_compound is None:
        return None, None
    key = str(source_compound).strip().upper()
    # Preserve source
    canonical = COMPOUND_ALIASES.get(key)
    if canonical is None:
        # Unknown, but preserve source_compound
        return CanonicalCompound.UNKNOWN, source_compound
    return canonical, source_compound
