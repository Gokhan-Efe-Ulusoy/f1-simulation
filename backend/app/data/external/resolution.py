"""Entity resolution with explicit MATCHED/AMBIGUOUS/UNMATCHED (Phase 22.5).

Never silently merges uncertain identities. Ambiguous aliases (one
normalized name mapping to several canonical IDs) are reported, not picked.
"""
from __future__ import annotations

from typing import Any

from app.data.resolution import AliasRegistry, normalize_name


class ResolutionOutcome(str):
    """Outcome constants (plain strings for JSON-friendly manifests)."""

    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


def resolve_with_aliases(
    raw_name: str,
    registries: list[AliasRegistry],
) -> dict[str, Any]:
    """Resolve one name against ordered registries.

    Returns {"status": MATCHED|AMBIGUOUS|UNMATCHED, "canonical_id": ...|None,
    "candidates": [...]}. AMBIGUOUS when several registries (or one
    registry with several owners) claim the name.
    """
    hits: list[str] = []
    for registry in registries:
        found = registry.resolve(raw_name)
        if found is not None and found not in hits:
            hits.append(found)
    if len(hits) == 1:
        return {"status": ResolutionOutcome.MATCHED, "canonical_id": hits[0], "candidates": hits}
    if len(hits) > 1:
        return {"status": ResolutionOutcome.AMBIGUOUS, "canonical_id": None, "candidates": hits}
    return {"status": ResolutionOutcome.UNMATCHED, "canonical_id": None, "candidates": []}


def build_driver_registry(canonical_drivers: list[dict[str, Any]]) -> AliasRegistry:
    """Build a driver alias registry from canonical driver rows."""
    registry = AliasRegistry()
    for driver in canonical_drivers:
        cid = str(driver.get("driver_id", ""))
        names = [str(driver.get("full_name", "")), cid, cid.replace("-", " ")]
        for alias in driver.get("aliases", []) or []:
            names.append(str(alias))
        # driverRef style: jolpica uses underscores (max_verstappen)
        names.append(cid.replace("-", "_"))
        if cid:
            try:
                registry.register_entity(cid, [n for n in names if n])
            except ValueError:
                continue  # conflicting alias: leave first owner, report downstream
    return registry


def build_driver_lookup(
    canonical_drivers: list[dict[str, Any]],
) -> tuple[AliasRegistry, dict[str, list[str]]]:
    """Build (registry, token -> [canonical_ids]) for driver resolution.

    The token index covers every whitespace-separated token of the
    normalized full name AND of the normalized canonical id, so short
    source refs ('gene', 'irvine', 'maldonado') match deterministically
    when the token is unique across drivers.
    """
    registry = build_driver_registry(canonical_drivers)
    by_last: dict[str, list[str]] = {}
    for driver in canonical_drivers:
        cid = str(driver.get("driver_id", ""))
        full = str(driver.get("full_name", "") or cid)
        tokens = set(normalize_name(full).split(" ")) | set(normalize_name(cid).split(" "))
        for token in tokens:
            if token and cid:
                by_last.setdefault(token, [])
                if cid not in by_last[token]:
                    by_last[token].append(cid)
    return registry, by_last


def season_driver_ids(canonical_results: list[dict[str, Any]]) -> dict[int, set[str]]:
    """Season -> set of canonical driver_ids appearing in results (evidence)."""
    out: dict[int, set[str]] = {}
    for row in canonical_results:
        try:
            season = int(str(row.get("race_id", ""))[:4])
        except ValueError:
            continue
        out.setdefault(season, set()).add(str(row.get("driver_id", "")))
    return out


def resolve_driver_ref(
    driver_ref: str,
    registry: AliasRegistry,
    by_last: dict[str, list[str]],
    season: int | None = None,
    season_drivers: dict[int, set[str]] | None = None,
) -> tuple[str | None, str]:
    """Resolve a source driver ref. Returns (canonical_id|None, status).

    Order: exact alias MATCHED; else unique last-name MATCHED; else, when a
    season is given, restrict same-surname candidates to drivers actually
    present in that season's canonical results (MATCHED iff exactly one);
    else AMBIGUOUS/UNMATCHED. Never guesses.
    """
    key = str(driver_ref).replace("_", "-")
    found = registry.resolve(key) or registry.resolve(str(driver_ref))
    if found is not None:
        return found, ResolutionOutcome.MATCHED
    tokens = normalize_name(key).split(" ")
    if len(tokens) == 1:
        candidates = by_last.get(tokens[0], [])
    else:
        sets = [set(by_last.get(tok, [])) for tok in tokens]
        candidates = sorted(set.intersection(*sets)) if all(sets) else []
    if len(candidates) == 1:
        return candidates[0], ResolutionOutcome.MATCHED
    if len(tokens) == 1 and len(candidates) > 1:
        # Surname preference (deterministic, documented): a single-token ref
        # (vintage Ergast style, e.g. 'davidson') matches the candidate whose
        # canonical surname equals the token, not a candidate carrying it as a
        # middle name (e.g. 'lewis-hamilton' <- 'Lewis Carl Davidson Hamilton').
        # Only upgrades to MATCHED when exactly one surname matches; otherwise
        # falls through to AMBIGUOUS. Never guesses.
        surname_hits = [c for c in candidates
                        if normalize_name(c).split(" ")[-1:] == [tokens[0]]]
        if len(surname_hits) == 1:
            return surname_hits[0], ResolutionOutcome.MATCHED
        if surname_hits:
            candidates = surname_hits
    if len(candidates) > 1 and season is not None and season_drivers is not None:
        present = [c for c in candidates if c in season_drivers.get(season, set())]
        if len(present) == 1:
            return present[0], ResolutionOutcome.MATCHED
        if present:
            return None, ResolutionOutcome.AMBIGUOUS
    if len(candidates) > 1:
        return None, ResolutionOutcome.AMBIGUOUS
    return None, ResolutionOutcome.UNMATCHED


def normalize_driver_ref(value: str) -> str:
    """Normalize a driver reference for joining (case/sep-insensitive)."""
    return normalize_name(str(value)).replace(" ", "-")


def summarize_resolutions(outcomes: list[dict[str, Any]]) -> dict[str, int]:
    """Count MATCHED/AMBIGUOUS/UNMATCHED outcomes."""
    summary = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}
    for outcome in outcomes:
        status = str(outcome.get("status", "UNMATCHED"))
        summary[status] = summary.get(status, 0) + 1
    return summary
