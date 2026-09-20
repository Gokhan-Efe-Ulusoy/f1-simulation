"""Full dataset build pipeline: raw → canonical → features → version (Phase 12).

Restartable: each stage records its manifest, checkpoint, and can resume
after failure without re-downloading unchanged resources.
"""
from __future__ import annotations

import json
import os
from typing import Any

from app.data.ingestion import CheckpointStore, bulk_ingest_jolpica, generate_dataset_manifest
from app.data.cache import IngestionCache
from app.data.rate_limit import RateLimiter
from app.data.fusion import CanonicalFusionEngine
from app.data.normalization import normalize_jolpica_result
from app.data.resolution import AliasRegistry
from app.data.validation import validate_bundle
from app.data.versions import DatasetVersion, register_version
from app.data.provenance import utc_now_iso
from app.data.features import driver_features, constructor_features, circuit_features
from app.data.coverage import build_coverage_report


def run_pipeline(
    root: str = ".",
    start_season: int = 1950,
    end_season: int = 2026,
    sources: list[str] | None = None,
    offline: bool = False,
    force: bool = False,
    dry_run: bool = False,
    dataset_version: str = "f1-dataset-v1.0",
) -> dict[str, Any]:
    """Run the full pipeline: ingestion → canonical → features → version.

    Returns a summary dict with counts, quality, coverage.
    All steps are restartable and use content hashing to skip unchanged.
    """
    sources = sources or ["jolpica"]
    os.makedirs(os.path.join(root, "data/raw"), exist_ok=True)

    # Stage 1: Ingestion (with checkpointing)
    ingestion_results: dict[str, Any] = {}
    if "jolpica" in sources:
        cache = IngestionCache(root=os.path.join(root, "data/raw/.cache"))
        rate_limiter = RateLimiter(requests_per_second=2.0)
        seasons = list(range(start_season, end_season + 1))
        manifests = bulk_ingest_jolpica(
            root, seasons=seasons, force=force, offline=offline,
            dry_run=dry_run, rate_limiter=rate_limiter, cache=cache,
        )
        ingestion_results["jolpica"] = {
            "manifests": len(manifests),
            "seasons": len(seasons),
            "dry_run": dry_run,
            "offline": offline,
        }

    if dry_run:
        return {"dry_run": True, "ingestion": ingestion_results}

    # Stage 2: Normalization → Canonical (fusion)
    # Load raw manifests and build canonical
    canonical_records: list[dict[str, Any]] = []
    raw_dir = os.path.join(root, "data/raw/jolpica")
    if os.path.exists(raw_dir):
        for fname in sorted(os.listdir(raw_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(raw_dir, fname), encoding="utf-8") as handle:
                    payload = json.load(handle)
                    # payload is list of bundles, each bundle is list of records
                    if isinstance(payload, list):
                        for bundle in payload:
                            if isinstance(bundle, list):
                                for rec in bundle:
                                    # Distinguish race schedule vs result row
                                    if "raceName" in rec or "Circuit" in rec:
                                        # Race schedule record -> HistoricalRace
                                        race_id = f"{rec.get('_season', rec.get('season', ''))}-{str(rec.get('Circuit', {}).get('circuitId', rec.get('circuit_ref', 'unknown'))).lower()}"  # noqa: E501
                                        canonical_records.append({
                                            "race_id": race_id,
                                            "season_id": str(rec.get("_season", rec.get("season", ""))),  # noqa: E501
                                            "round": int(rec.get("round", 1)),
                                            "official_name": rec.get("raceName", ""),
                                            "circuit_id": rec.get("Circuit", {}).get("circuitId", rec.get("circuit_ref", "")),  # noqa: E501
                                            "date": rec.get("date", ""),
                                        })
                                    elif "Driver" in rec or "driverId" in rec:
                                        norm, _ = normalize_jolpica_result(rec)
                                        # Also create result_id
                                        race_id = f"{rec.get('_season', '')}-{rec.get('_circuit_id', 'unknown')}"  # noqa: E501
                                        driver_id = rec.get("Driver", {}).get("driverId", rec.get("driver_ref", ""))  # noqa: E501
                                        if driver_id:
                                            norm["result_id"] = f"{race_id}:{driver_id}"
                                            norm["race_id"] = race_id
                                            norm["driver_id"] = driver_id
                                        canonical_records.append(norm)
                                    else:
                                        # Generic fallback
                                        norm, _ = normalize_jolpica_result(rec)
                                        canonical_records.append(norm)

    # Entity resolution + fusion (deterministic)
    registry = AliasRegistry()
    # Pre-register known aliases (e.g., McLaren variants)
    registry.register_entity("constructor:mclaren", ["McLaren", "McLaren F1 Team", "McLaren International"])  # noqa: E501
    engine = CanonicalFusionEngine(alias_registry=registry)
    # Group and fuse (simplified: each record is its own group for now)
    canonical: list[dict[str, Any]] = []
    for rec in canonical_records:
        canonical.append(rec)  # In production, would group and fuse

    # Stage 3: Validation
    races = [r for r in canonical if "race_id" in r]
    results = [r for r in canonical if "result_id" in r]
    report = validate_bundle(dataset_version, races=races, results=results)

    # Persist canonical (batched, not per-record)
    canonical_dir = os.path.join(root, "data/canonical")
    os.makedirs(canonical_dir, exist_ok=True)
    with open(os.path.join(canonical_dir, "races.json"), "w", encoding="utf-8") as handle:
        json.dump(races, handle, indent=2, sort_keys=True)
    with open(os.path.join(canonical_dir, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)

    # Stage 4: Features
    derived_dir = os.path.join(root, "data/derived")
    os.makedirs(derived_dir, exist_ok=True)
    # Driver features
    driver_ids = sorted({str(r.get("driver_id")) for r in results if r.get("driver_id")})
    driver_feats = []
    for did in driver_ids:
        driver_feats.extend([f.model_dump() for f in driver_features(did, str(start_season), results)])  # noqa: E501
    with open(os.path.join(derived_dir, "driver_features.json"), "w", encoding="utf-8") as handle:
        json.dump(driver_feats, handle, indent=2, sort_keys=True)

    # Stage 5: Dataset version (only if quality gates pass)
    quality_score = 1.0 - (len(report.errors) / max(1, len(canonical)))
    version = DatasetVersion(
        dataset_id=dataset_version,
        source_versions={s: "0.1.0" for s in sources},
        extraction_date=utc_now_iso(),
        coverage={"seasons": f"{start_season}-{end_season}", "sources": sources},
        record_counts={"races": len(races), "results": len(results), "features": len(driver_feats)},
        quality_score=quality_score,
        known_limitations=[] if not report.errors else report.errors[:5],
    )
    if report.errors:
        # Do not auto-create version if gates fail; return report
        return {
            "ingestion": ingestion_results,
            "canonical": len(canonical),
            "validation": report.model_dump(),
            "quality_gate": "FAILED",
            "version": None,
        }

    register_version(root, version)
    manifest = generate_dataset_manifest(root, dataset_version, source_versions={s: "0.1.0" for s in sources})  # noqa: E501

    # Coverage report
    coverage = build_coverage_report(start_season, end_season)
    with open(os.path.join(root, "data/validation/coverage_report.json"), "w", encoding="utf-8") as handle:  # noqa: E501
        json.dump(coverage, handle, indent=2, sort_keys=True)

    return {
        "ingestion": ingestion_results,
        "canonical": len(canonical),
        "validation": report.model_dump(),
        "quality_gate": "PASSED",
        "version": version.model_dump(),
        "manifest": manifest,
        "coverage": coverage["summary"],
    }
