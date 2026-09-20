"""Canonical fusion engine: multi-source → canonical (Phase 10F).

Pipeline: Raw Sources → Normalize → Resolve Entities → Match Records
→ Compare Fields → Detect Conflicts → Apply Source Policy → Create
Canonical Record → Attach Provenance → Validate → Persist.

Field-level source priority is configurable per dataset version.
Provenance chains are preserved end-to-end.
"""
from __future__ import annotations

from typing import Any

from app.data.catalog import SourceCatalog, default_catalog
from app.data.conflicts import DataConflict, compare_fact, detect_conflicts
from app.data.models.canonical import DataProvenance
from app.data.normalization import normalize_jolpica_result
from app.data.provenance import make_provenance
from app.data.resolution import AliasRegistry
from app.data.validation import validate_bundle


class CanonicalFusionEngine:
    """Fuses normalized records from multiple sources into canonical records."""

    def __init__(
        self,
        catalog: SourceCatalog | None = None,
        alias_registry: AliasRegistry | None = None,
    ) -> None:
        self.catalog = catalog or default_catalog()
        self.alias_registry = alias_registry or AliasRegistry()
        self.conflicts: list[DataConflict] = []
        self.warnings: list[str] = []

    def normalize_bundle(self, bundle, source_provider: str) -> tuple[list[dict[str, Any]], list[str]]:  # noqa: E501
        """Normalize a raw bundle (source-specific → common shape)."""
        normalized: list[dict[str, Any]] = []
        all_warnings: list[str] = []
        for row in bundle.records:
            if source_provider in ("jolpica", "official_f1", "fia"):
                rec, warns = normalize_jolpica_result(row)
            else:
                # Generic: pass through with basic cleaning
                rec, warns = {"raw": row, "source": source_provider}, []
            # Attach provenance
            prov = make_provenance(
                source_provider=source_provider,
                source_record_id=str(row.get("_source_file", row.get("driverId", ""))),
                raw_payload=row,
                steps=["normalize"],
            )
            rec["_provenance"] = prov.model_dump()
            normalized.append(rec)
            all_warnings.extend(warns)
        return normalized, all_warnings

    def match_records(
        self, normalized_bundles: list[list[dict[str, Any]]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group normalized records by entity key (race_id:driver_id etc).

        Uses contextual keys: season, race, date, circuit, constructor, driver
        where available. Never merges on fuzzy name alone.
        Prefer race_id when present (most stable).
        """
        groups: dict[str, list[dict[str, Any]]] = {}
        for bundle in normalized_bundles:
            for rec in bundle:
                # Prefer explicit race_id/result_id if present
                race_id = rec.get("race_id") or rec.get("_race_id") or ""
                if race_id:
                    driver = rec.get("driver_ref", rec.get("driver_id", rec.get("_winner", "")))
                    resolved = self.alias_registry.resolve(str(driver)) or str(driver) if driver else ""  # noqa: E501
                    key = f"{race_id}:{resolved}" if resolved else str(race_id)
                else:
                    season = rec.get("season", rec.get("_season", ""))
                    rnd = rec.get("round", rec.get("_round", ""))
                    driver = rec.get("driver_ref", rec.get("driver_id", rec.get("_winner", "")))
                    resolved = self.alias_registry.resolve(str(driver)) or str(driver) if driver else ""  # noqa: E501
                    key = f"{season}:{rnd}:{resolved}"
                if not key.strip(":"):
                    key = f"unknown:{len(groups)}"
                groups.setdefault(key, []).append(rec)
        return groups

    def fuse_field(
        self, field: str, values_by_provider: dict[str, Any]
    ) -> tuple[Any, DataConflict | None]:
        """Fuse one field across providers using field-level priority."""
        # Convert to string for comparison
        str_values = {k: str(v) for k, v in values_by_provider.items()}
        if len(set(str_values.values())) <= 1:
            # Agreement
            return (next(iter(values_by_provider.values())) if values_by_provider else None), None

        conflict = compare_fact(
            entity_id=field,
            field=field,
            provider_values=str_values,
            priority=self.catalog.priority_for_field(field),
        )
        if conflict:
            self.conflicts.append(conflict)
            # Return resolved value (from priority)
            # Find original value for resolved provider
            for provider, val in values_by_provider.items():
                if str(val) == conflict.resolution:
                    return val, conflict
        return None, conflict

    def fuse_group(self, group: list[dict[str, Any]]) -> dict[str, Any]:
        """Fuse one matched group into a canonical record."""
        if not group:
            return {}
        if len(group) == 1:
            rec = dict(group[0])
            # Extend provenance chain
            if "_provenance" in rec:
                prov = DataProvenance(**rec["_provenance"])
                rec["_provenance"] = prov.extended("fuse").model_dump()
            return rec

        # Multi-source: field-by-field fusion
        all_fields = set()
        for rec in group:
            all_fields.update(k for k in rec.keys() if not k.startswith("_"))

        canonical: dict[str, Any] = {}
        provenance_chains: list[str] = []
        for field in sorted(all_fields):
            values_by_provider: dict[str, Any] = {}
            for rec in group:
                if field in rec and rec[field] is not None:
                    prov = rec.get("_provenance", {})
                    provider = prov.get("source_provider", "unknown") if isinstance(prov, dict) else "unknown"  # noqa: E501
                    values_by_provider[provider] = rec[field]
                    if isinstance(prov, dict) and prov.get("transformation_chain"):
                        provenance_chains.extend(prov["transformation_chain"])

            fused_val, _ = self.fuse_field(field, values_by_provider)
            canonical[field] = fused_val

        # Attach merged provenance
        canonical["_provenance"] = make_provenance(
            source_provider="fusion",
            source_record_id=canonical.get("race_id", ""),
            steps=sorted(set(provenance_chains + ["fuse"])),
        ).model_dump()
        canonical["_source_count"] = len(group)
        return canonical

    def fuse_all(
        self, normalized_bundles: list[list[dict[str, Any]]]
    ) -> tuple[list[dict[str, Any]], list[DataConflict]]:
        """Fuse all groups; returns (canonical_records, conflicts)."""
        groups = self.match_records(normalized_bundles)
        canonical: list[dict[str, Any]] = []
        for group in groups.values():
            rec = self.fuse_group(group)
            if rec:
                canonical.append(rec)
        return canonical, list(self.conflicts)

    def validate_canonical(
        self, canonical: list[dict[str, Any]], dataset_version: str = "v1"
    ) -> Any:
        """Run quality validation on canonical records."""
        # Convert to expected bundle format for validation
        races = [r for r in canonical if "race_id" in r]
        results = [r for r in canonical if "result_id" in r]
        return validate_bundle(dataset_version, races=races, results=results)

    def detect_cross_source_conflicts(
        self, facts: list[tuple[str, str, dict[str, str]]]
    ) -> list[DataConflict]:
        """Detect conflicts across sources for given facts."""
        conflicts = detect_conflicts(facts, priority=None)
        self.conflicts.extend(conflicts)
        return conflicts
