"""Historical dataset builder: canonical dataset assembly (Phase 10G).

Builds 1950-2026 canonical dataset from normalized bundles.
Handles bulk inserts, batching, and persistence.
"""
from __future__ import annotations

import json
import os
from typing import Any

from app.data.provenance import utc_now_iso
from app.data.validation import validate_bundle
from app.data.versions import DatasetVersion, register_version


class DatasetBuilder:
    """Builds canonical dataset from normalized sources."""

    def __init__(self, root: str = ".") -> None:
        self.root = root
        self.canonical_records: list[dict[str, Any]] = []
        self.conflicts: list[Any] = []

    def add_canonical(self, records: list[dict[str, Any]]) -> None:
        """Add canonical records (bulk insert simulation)."""
        # Batch-oriented: extend, not one-by-one DB transactions
        self.canonical_records.extend(records)

    def build(
        self,
        dataset_version: str,
        source_versions: dict[str, str] | None = None,
        batch_size: int = 1000,
    ) -> DatasetVersion:
        """Build and persist canonical dataset with validation.

        Uses batching to avoid one transaction per record.
        Returns the registered dataset version.
        """
        canonical_dir = os.path.join(self.root, "data/canonical")
        os.makedirs(canonical_dir, exist_ok=True)

        # Batch persistence (simulate bulk insert)
        # Group by entity type for storage
        by_type: dict[str, list[dict[str, Any]]] = {}
        for rec in self.canonical_records:
            # Determine entity type by ID field
            if "race_id" in rec and "driver_id" not in rec:
                by_type.setdefault("races", []).append(rec)
            elif "driver_id" in rec and "race_id" in rec:
                by_type.setdefault("results", []).append(rec)
            elif "driver_id" in rec:
                by_type.setdefault("drivers", []).append(rec)
            elif "constructor_id" in rec:
                by_type.setdefault("constructors", []).append(rec)
            elif "circuit_id" in rec:
                by_type.setdefault("circuits", []).append(rec)
            else:
                by_type.setdefault("other", []).append(rec)

        record_counts: dict[str, int] = {}
        for entity_type, records in by_type.items():
            # Batch write
            path = os.path.join(canonical_dir, f"{entity_type}.json")
            # Read existing if any (incremental)
            existing = []
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    existing = json.load(handle)
            # Deduplicate by ID field
            seen_ids = {r.get("race_id") or r.get("result_id") or r.get("driver_id") or str(id(r))
                        for r in existing}
            new_records = []
            for rec in records:
                rid = rec.get("race_id") or rec.get("result_id") or rec.get("driver_id") or str(id(rec))  # noqa: E501
                if rid not in seen_ids:
                    new_records.append(rec)
                    seen_ids.add(rid)

            combined = existing + new_records
            # Write in batches (simulate bulk)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(combined, handle, indent=2, sort_keys=True)
            record_counts[entity_type] = len(combined)

        # Validation
        races = by_type.get("races", [])
        results = by_type.get("results", [])
        drivers = by_type.get("drivers", [])
        constructors = by_type.get("constructors", [])
        report = validate_bundle(dataset_version, races=races, results=results,
                                 drivers=drivers, constructors=constructors)

        # Write quality report
        validation_dir = os.path.join(self.root, "data/validation")
        os.makedirs(validation_dir, exist_ok=True)
        with open(os.path.join(validation_dir, "report.json"), "w", encoding="utf-8") as handle:
            json.dump(report.model_dump(), handle, indent=2, sort_keys=True)

        # Write conflicts if any
        if self.conflicts:
            with open(os.path.join(validation_dir, "conflicts.json"), "w", encoding="utf-8") as handle:  # noqa: E501
                json.dump([c.model_dump() for c in self.conflicts], handle, indent=2, sort_keys=True)  # noqa: E501

        # Register dataset version
        version = DatasetVersion(
            dataset_id=dataset_version,
            source_versions=source_versions or {},
            extraction_date=utc_now_iso(),
            record_counts=record_counts,
            quality_score=1.0 - (len(report.errors) / max(1, sum(record_counts.values()))),
        )
        register_version(self.root, version)

        # Generate dataset manifest
        from app.data.ingestion import generate_dataset_manifest
        generate_dataset_manifest(self.root, dataset_version, source_versions)

        return version

    def get_coverage_summary(self) -> dict[str, Any]:
        """Return coverage summary for the built dataset."""
        from app.data.coverage import build_coverage_report
        return build_coverage_report()
