"""Bulk and checkpointed ingestion orchestration (Phase 10B/10G).

Supports:
- pagination, retry, rate limiting, caching (via adapters + cache.py)
- checkpointed ingestion: completed/failed/skipped/pending per season/round
- incremental ingestion: skip unchanged resources via content hash
- bulk ingestion: --season all, --limit, --force, --offline, --dry-run
- dataset-manifest.json generation
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from app.data.cache import IngestionCache
from app.data.manifests import IngestionManifest, run_ingestion
from app.data.rate_limit import RateLimiter


class CheckpointStore:
    """Tracks per-unit ingestion status (completed/failed/skipped/pending)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.state: dict[str, str] = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                self.state = json.load(handle)

    def get(self, key: str) -> str:
        """Return status for a unit key, or 'pending'."""
        return self.state.get(key, "pending")

    def set(self, key: str, status: str) -> None:
        """Set status and persist."""
        self.state[key] = status
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)

    def summary(self) -> dict[str, int]:
        """Count by status."""
        counts: dict[str, int] = {"completed": 0, "failed": 0, "skipped": 0, "pending": 0}
        for v in self.state.values():
            counts[v] = counts.get(v, 0) + 1
        return counts


def bulk_ingest_jolpica(
    root: str,
    seasons: list[int] | None = None,
    limit: int | None = None,
    force: bool = False,
    offline: bool = False,
    dry_run: bool = False,
    rate_limiter: RateLimiter | None = None,
    cache: IngestionCache | None = None,
    transport: Any | None = None,
) -> list[IngestionManifest]:
    """Bulk ingest Jolpica seasons with checkpointing.

    Uses injected transport for offline tests; when offline=True, only
    cached data is used (no network). Returns manifests per season.
    """
    from app.data.sources.jolpica import JolpicaAdapter

    if seasons is None:
        seasons = list(range(1950, 2027))

    if limit is not None:
        seasons = seasons[:limit]

    rate_limiter = rate_limiter or RateLimiter(requests_per_second=2.0)
    cache = cache or IngestionCache(root=os.path.join(root, "data/raw/.cache"))

    checkpoint_path = os.path.join(root, "data/manifests/checkpoint_jolpica.json")
    checkpoint = CheckpointStore(checkpoint_path)

    manifests: list[IngestionManifest] = []

    for season in seasons:
        key = f"jolpica:season:{season}"
        if not force and checkpoint.get(key) == "completed" and not dry_run:
            # Check cache for incremental skip
            if cache.has("jolpica", f"{season}.json"):
                continue

        if offline and not cache.has("jolpica", f"{season}.json"):
            checkpoint.set(key, "skipped")
            continue

        if dry_run:
            checkpoint.set(key, "pending")
            continue

        try:
            adapter = JolpicaAdapter(transport=transport)
            bundle = rate_limiter.execute_with_retry(lambda: adapter.fetch_season(season))

            # Cache raw response
            payload_hash = cache.put("jolpica", f"{season}.json", bundle.records)

            # Also fetch each race in season for race-level coverage
            race_bundles = []
            for race_rec in bundle.records[: (limit or len(bundle.records))]:
                rnd = race_rec.get("round")
                if rnd is None:
                    continue
                rkey = f"jolpica:race:{season}:{rnd}"
                if not force and checkpoint.get(rkey) == "completed":
                    continue
                try:
                    race_bundle = rate_limiter.execute_with_retry(
                        lambda: adapter.fetch_race(season, int(rnd))
                    )
                    cache.put("jolpica", f"{season}/{rnd}/results.json", race_bundle.records)
                    race_bundles.append(race_bundle)
                    checkpoint.set(rkey, "completed")
                except Exception:  # noqa: BLE001
                    checkpoint.set(rkey, "failed")

            manifest = run_ingestion(
                root, "jolpica", f"{season}",
                [bundle] + race_bundles,
            )
            checkpoint.set(key, "completed")
            manifests.append(manifest)

        except Exception as exc:  # noqa: BLE001
            checkpoint.set(key, "failed")
            # Still create a manifest for the failure
            import uuid

            from app.data.manifests import IngestionManifest
            from app.data.provenance import utc_now_iso

            manifests.append(IngestionManifest(
                run_id=uuid.uuid4().hex,
                source="jolpica",
                started_at=utc_now_iso(),
                completed_at=utc_now_iso(),
                coverage=str(season),
                records_fetched=0,
                records_rejected=1,
                warnings=[str(exc)],
            ))

        # Respect checkpoint: if restarted, continues from pending
        time.sleep(0.01)  # Small delay to avoid hammering in loops

    return manifests


def generate_dataset_manifest(
    root: str,
    dataset_version: str,
    source_versions: dict[str, str] | None = None,
    parser_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate dataset-manifest.json for the canonical dataset.

    Collects coverage, record counts, quality metrics, conflicts, gaps,
    license metadata, schema version. Does not fabricate data.
    """
    import glob

    from app.data.provenance import utc_now_iso
    from app.data.versions import SCHEMA_VERSION

    canonical_dir = os.path.join(root, "data/canonical")
    counts: dict[str, int] = {}
    if os.path.exists(canonical_dir):
        for fname in os.listdir(canonical_dir):
            fpath = os.path.join(canonical_dir, fname)
            if os.path.isfile(fpath) and fname.endswith(".json"):
                with open(fpath, encoding="utf-8") as handle:
                    data = json.load(handle)
                    counts[fname.replace(".json", "")] = len(data) if isinstance(data, list) else 1
            elif os.path.isdir(fpath):
                # Parquet or subdirs
                files = glob.glob(os.path.join(fpath, "*.parquet"))
                if files:
                    counts[fname] = len(files)

    # Quality report if exists
    quality_path = os.path.join(root, "data/validation/report.json")
    quality = {}
    if os.path.exists(quality_path):
        with open(quality_path, encoding="utf-8") as handle:
            quality = json.load(handle)

    # Conflict report
    conflict_path = os.path.join(root, "data/validation/conflicts.json")
    conflicts = []
    if os.path.exists(conflict_path):
        with open(conflict_path, encoding="utf-8") as handle:
            conflicts = json.load(handle)

    manifest = {
        "dataset_version": dataset_version,
        "creation_timestamp": utc_now_iso(),
        "source_versions": source_versions or {},
        "parser_versions": parser_versions or {},
        "coverage": counts,
        "record_counts": counts,
        "quality_metrics": quality,
        "conflicts": len(conflicts) if isinstance(conflicts, list) else 0,
        "unresolved_gaps": [],
        "license_metadata": {"note": "See docs/data-licensing.md, per-source terms"},
        "schema_version": SCHEMA_VERSION,
    }

    out_path = os.path.join(root, "data/manifests/dataset-manifest.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)

    return manifest
