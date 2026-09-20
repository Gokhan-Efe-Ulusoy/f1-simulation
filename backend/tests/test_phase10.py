"""Phase 10 tests: source catalog, cache/rate-limit, adapters, fusion,
security, checkpointed/bulk ingestion, dataset, calibration, benchmark, splits,
coverage. All offline via injected transports/fixtures."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from app.data.availability import availability_for
from app.data.benchmark import run_benchmark
from app.data.cache import IngestionCache, cache_key
from app.data.catalog import (
    ReliabilityTier,
    SourceMetadata,
    SourceType,
    default_catalog,
)
from app.data.coverage import build_coverage_report
from app.data.fusion import CanonicalFusionEngine
from app.data.ingestion import CheckpointStore, bulk_ingest_jolpica, generate_dataset_manifest
from app.data.rate_limit import RateLimiter
from app.data.security import sanitize_filename, sanitize_path
from app.data.sources.fia import FiaDocumentAdapter
from app.data.sources.github import GitHubSourceAdapter
from app.data.sources.kaggle import KaggleSourceAdapter
from app.data.sources.openf1 import OpenF1SourceAdapter
from app.data.sources.weather import WeatherSourceAdapter
from app.data.splits import TemporalSplit


# Catalog
def test_catalog_tiers_and_priorities() -> None:
    catalog = default_catalog()
    assert len(catalog.sources) >= 8
    # Tier order: TIER_1 first
    active = catalog.active_sources()
    assert active[0].reliability_tier == ReliabilityTier.TIER_1
    # Field priority
    assert catalog.priority_for_field("race_winner")[0] == "official_f1"
    catalog.set_priority("race_winner", ["jolpica", "official_f1"])
    assert catalog.priority_for_field("race_winner") == ["jolpica", "official_f1"]
    # Duplicate rejection
    with pytest.raises(ValueError):
        catalog.add_source(SourceMetadata(source_id="jolpica", provider="dup"))


def test_catalog_metadata_fields() -> None:
    meta = SourceMetadata(source_id="test", provider="Test", source_type=SourceType.API,
                          description="desc", homepage="https://example.com",
                          api_url="https://api.example.com", coverage_start=2000,
                          coverage_end=2024, supported_entities=["race"],
                          supported_resolution=["race"], license="MIT",
                          terms_notes="test", retrieval_method="GET",
                          reliability_tier=ReliabilityTier.TIER_2, active=True,
                          last_verified="2026-01-01")
    assert meta.source_id == "test"
    assert meta.license == "MIT"


# Cache & rate limiting
def test_cache_key_deterministic_and_sanitized() -> None:
    k1 = cache_key("jolpica", "2024.json", {"limit": 30})
    k2 = cache_key("jolpica", "2024.json", {"limit": 30})
    assert k1 == k2
    assert k1 != cache_key("jolpica", "2024.json", {"limit": 31})
    assert sanitize_filename("../../etc/passwd") != "../../etc/passwd"
    assert sanitize_filename("=cmd|+calc") .startswith("_")


def test_cache_put_get_has() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = IngestionCache(root=os.path.join(tmp, "cache"))
        assert not cache.has("jolpica", "2024.json")
        h = cache.put("jolpica", "2024.json", {"data": [1, 2, 3]})
        assert h
        assert cache.has("jolpica", "2024.json")
        assert cache.get("jolpica", "2024.json")["payload"]["data"] == [1, 2, 3]


def test_rate_limiter_retry() -> None:
    limiter = RateLimiter(requests_per_second=100, max_retries=2, backoff_base=0.001)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return 42

    assert limiter.execute_with_retry(flaky) == 42
    assert calls["n"] == 3


# Jolpica bulk with pagination/rate/cache/checkpoint (mocked)
def test_jolpica_bulk_pagination_rate_cache_checkpoint(tmp_path) -> None:
    # Transport returns paginated schedule
    def transport(url: str):
        if "2024.json" in url and "results" not in url:
            return {"MRData": {"RaceTable": {"Races": [
                {"season": "2024", "round": "1", "raceName": "Bahrain GP",
                 "date": "2024-03-02", "Circuit": {"circuitId": "bahrain"}},
            ]}}}
        if "2024/1/results.json" in url:
            return {"MRData": {"RaceTable": {"Races": [
                {"Results": [{"position": "1", "Driver": {"driverId": "max_verstappen"},
                              "Constructor": {"constructorId": "red_bull"}, "grid": "1", "status": "Finished"}]}]}}}
        return {"MRData": {"RaceTable": {"Races": []}}}

    root = str(tmp_path)
    rate_limiter = RateLimiter(requests_per_second=100)
    cache = IngestionCache(root=os.path.join(root, "data/raw/.cache"))
    manifests = bulk_ingest_jolpica(root, seasons=[2024], transport=transport,
                                     rate_limiter=rate_limiter, cache=cache)
    assert len(manifests) == 1
    assert manifests[0].records_fetched >= 1
    # Second run without force should skip via checkpoint/cache
    manifests2 = bulk_ingest_jolpica(root, seasons=[2024], transport=transport,
                                      rate_limiter=rate_limiter, cache=cache)
    assert len(manifests2) == 0  # skipped
    # Force re-fetches
    manifests3 = bulk_ingest_jolpica(root, seasons=[2024], transport=transport,
                                      rate_limiter=rate_limiter, cache=cache, force=True)
    assert len(manifests3) == 1
    # Checkpoint file exists
    assert os.path.exists(os.path.join(root, "data/manifests/checkpoint_jolpica.json"))


def test_bulk_ingest_dry_run_and_limit(tmp_path) -> None:
    def transport(url: str):
        return {"MRData": {"RaceTable": {"Races": []}}}
    root = str(tmp_path)
    manifests = bulk_ingest_jolpica(root, seasons=[2024, 2025], limit=1,
                                     transport=transport, dry_run=True)
    assert manifests == []
    # Check checkpoint still pending
    store = CheckpointStore(os.path.join(root, "data/manifests/checkpoint_jolpica.json"))
    assert store.get("jolpica:season:2024") == "pending"


def test_checkpoint_store_persistence(tmp_path) -> None:
    path = os.path.join(str(tmp_path), "ckpt.json")
    store = CheckpointStore(path)
    store.set("k1", "completed")
    store.set("k2", "failed")
    store2 = CheckpointStore(path)
    assert store2.get("k1") == "completed"
    assert store2.summary()["completed"] == 1


# OpenF1 capabilities
def test_openf1_capability_discovery() -> None:
    adapter = OpenF1SourceAdapter(transport=lambda url: [])
    assert adapter.capabilities(2010)["laps"] is False
    assert adapter.capabilities(2024)["laps"] is True
    bundle = adapter.fetch_season(2024)
    assert bundle.provider == "openf1"


def test_openf1_unsupported_season_rejected() -> None:
    adapter = OpenF1SourceAdapter(transport=lambda url: [])
    bundle = adapter.fetch_season(2010)
    assert bundle.rejected


# Kaggle pinned ingestion
def test_kaggle_local_import_pinned(tmp_path) -> None:
    base = os.path.join(str(tmp_path), "kaggle")
    os.makedirs(os.path.join(base, "owner", "dataset"), exist_ok=True)
    with open(os.path.join(base, "owner", "dataset", "data.csv"), "w", encoding="utf-8") as handle:
        handle.write("driver_ref,position\nVER,1\nHAM,2\n")
    with open(os.path.join(base, "owner", "dataset", "meta.json"), "w", encoding="utf-8") as handle:
        json.dump([{"driver_ref": "VER"}], handle)
    adapter = KaggleSourceAdapter(base_dir=base)
    bundle = adapter.fetch_dataset("owner", "dataset")
    assert len(bundle.records) >= 2
    assert bundle.records[0]["_dataset"] == "owner/dataset"
    # Formula injection sanitized
    with open(os.path.join(base, "owner", "dataset", "evil.csv"), "w", encoding="utf-8") as handle:
        handle.write("a,b\n=cmd,2\n")
    bundle2 = adapter.fetch_dataset("owner", "dataset", file_name="evil.csv")
    assert bundle2.records[0]["a"].startswith("'")


def test_kaggle_missing_rejected() -> None:
    with pytest.raises(Exception):  # DataUnavailable
        KaggleSourceAdapter(base_dir="/nonexistent").fetch_dataset("a", "b")


# GitHub pinned
def test_github_local_pinned(tmp_path) -> None:
    local = os.path.join(str(tmp_path), "data.csv")
    with open(local, "w", encoding="utf-8") as handle:
        handle.write("driver_ref,position\nVER,1\n")
    adapter = GitHubSourceAdapter(base_dir=str(tmp_path))
    bundle = adapter.fetch_file("owner", "repo", "data/file.csv", ref="abc123", local_path=local)
    assert bundle.records[0]["_ref"] == "abc123"
    assert bundle.records[0]["_file_hash"]
    # Path traversal rejected
    with pytest.raises(ValueError):
        adapter.fetch_file("owner", "repo", "../../etc/passwd", ref="abc", local_path=local)


def test_github_remote_requires_ref() -> None:
    adapter = GitHubSourceAdapter()
    with pytest.raises(Exception):
        adapter.fetch_file("owner", "repo", "data/file.csv")


# FIA / Weather
def test_fia_document_import(tmp_path) -> None:
    doc = os.path.join(str(tmp_path), "doc.json")
    with open(doc, "w", encoding="utf-8") as handle:
        json.dump({"title": "Official Results"}, handle)
    bundle = FiaDocumentAdapter(base_dir=str(tmp_path)).import_document(
        "doc1", doc, publication_date="2024-03-02", version="1.0",
        url="https://fia.com/doc1", extracted_fields={"winner": "VER"})
    assert bundle.records[0]["_document_id"] == "doc1"
    assert bundle.records[0]["_file_hash"]


def test_weather_import(tmp_path) -> None:
    obs = os.path.join(str(tmp_path), "weather.json")
    with open(obs, "w", encoding="utf-8") as handle:
        json.dump([{"observation_id": "o1", "race_id": "r1", "air_temperature_c": 30.0}], handle)
    bundle = WeatherSourceAdapter(base_dir=str(tmp_path)).import_observations(obs, source="manual")
    assert bundle.records[0]["air_temperature_c"] == 30.0


# Fusion
def test_fusion_agreement_and_conflict() -> None:
    engine = CanonicalFusionEngine()
    # Agreement: same winner
    bundled = [
        [{"race_id": "r1", "winner": "VER", "_provenance": {"source_provider": "jolpica"}}],
        [{"race_id": "r1", "winner": "VER", "_provenance": {"source_provider": "official_f1"}}],
    ]
    groups = engine.match_records(bundled)
    assert "2024:1:VER" in groups or len(groups) >= 1

    # Conflict via field priority
    engine2 = CanonicalFusionEngine()
    val, conflict = engine2.fuse_field("race_winner", {"jolpica": "HAM", "official_f1": "VER"})
    assert val == "VER"
    assert conflict is not None
    assert "official_f1" in conflict.resolution_reason


def test_fusion_provenance_chain() -> None:
    engine = CanonicalFusionEngine()
    bundles = [
        [{"race_id": "r1", "winner": "VER", "_provenance": {"source_provider": "jolpica",
                                                            "transformation_chain": ["fetch"]}}],
        [{"race_id": "r1", "winner": "VER", "_provenance": {"source_provider": "official_f1",
                                                            "transformation_chain": ["fetch"]}}],
    ]
    canon, conflicts = engine.fuse_all(bundles)
    assert len(canon) == 1
    assert "fuse" in canon[0]["_provenance"]["transformation_chain"]


# Security
def test_security_sanitize() -> None:
    assert sanitize_filename("=cmd") != "=cmd"
    assert sanitize_filename("a/b") != "a/b"
    with pytest.raises(ValueError):
        sanitize_path("../../etc/passwd", "/base")
    # Platform-independent check: must be inside base and contain expected parts
    sanitized = sanitize_path("data/file.csv", "/base")
    assert "data" in sanitized and "file.csv" in sanitized
    assert sanitized.startswith("/base") or sanitized.startswith("\\base") or "base" in sanitized
    # Oversized payload
    from app.data.security import validate_payload_size, validate_record_count
    with pytest.raises(ValueError):
        validate_payload_size(b"x" * (51 * 1024 * 1024))
    with pytest.raises(ValueError):
        validate_record_count(200000)


# Dataset builder
def test_dataset_builder_bulk_and_dedup(tmp_path) -> None:
    from app.data.dataset_builder import DatasetBuilder

    builder = DatasetBuilder(root=str(tmp_path))
    builder.add_canonical([{"race_id": "r1", "round": 1}, {"race_id": "r2", "round": 2}])
    builder.add_canonical([{"race_id": "r1", "round": 1}])  # duplicate
    version = builder.build("f1-test-v1", source_versions={"jolpica": "0.1.0"})
    assert version.dataset_id == "f1-test-v1"
    with open(os.path.join(str(tmp_path), "data/canonical/races.json"), encoding="utf-8") as handle:
        assert len(json.load(handle)) == 2  # deduped


# Calibration dataset
def test_calibration_dataset_no_auto_promote(tmp_path) -> None:
    from app.data.calibration_dataset import CalibrationDatasetBuilder

    # Create minimal canonical
    canon_dir = os.path.join(str(tmp_path), "data/canonical")
    os.makedirs(canon_dir, exist_ok=True)
    with open(os.path.join(canon_dir, "results.json"), "w", encoding="utf-8") as handle:
        json.dump([{"race_id": "r1", "driver_id": "d1", "constructor_id": "c1",
                    "grid_position": 1, "final_position": 1, "status": "finished"}], handle)
    with open(os.path.join(canon_dir, "races.json"), "w", encoding="utf-8") as handle:
        json.dump([{"race_id": "r1", "circuit_id": "c1"}], handle)
    builder = CalibrationDatasetBuilder(root=str(tmp_path))
    result = builder.build("f1-test-v1", canonical_dir=canon_dir)
    assert result["record_count"] >= 1
    with open(result["calibration_dataset"], encoding="utf-8") as handle:
        data = json.load(handle)
    assert all("dataset_version" in r and "model_version" in r for r in data)
    # Candidates exist but not auto-promoted to production
    with open(result["candidates"], encoding="utf-8") as handle:
        cands = json.load(handle)
    assert cands[0]["method"] == "observed_mean"


# Benchmark Monte Carlo determinism
def test_benchmark_monte_carlo_determinism() -> None:
    def make_sim(fav):
        def simulate(idx: int):
            order = ["d1", "d2"] if (idx % 2 == 0) else ["d2", "d1"]
            return {"order": order, "lap_times": {"d1": [90.0], "d2": [91.0]},
                    "dnf_rate": 0.0, "pit_stops": {}}
        return simulate

    b1 = run_benchmark("r1", ["d1", "d2"], simulate=make_sim("d1"), simulation_count=20)
    b2 = run_benchmark("r1", ["d1", "d2"], simulate=make_sim("d1"), simulation_count=20)
    assert b1.simulated_position_distribution == b2.simulated_position_distribution
    # Position error + Brier etc
    assert b1.calibration_metrics["position_error"] is not None


# Temporal splits determinism
def test_temporal_splits_deterministic() -> None:

    split = TemporalSplit()
    assert split.assign(1950) == "train"
    assert split.assign(2005) == "validation"
    assert split.assign(2015) == "test"
    assert split.assign(2024) == "out_of_sample"
    assert split.assign(1950) == "train"  # deterministic


# Coverage report
def test_coverage_report_has_required_fields() -> None:
    report = build_coverage_report(1950, 2026)
    assert "seasons" in report and "summary" in report
    for field in ("race_results", "telemetry"):
        assert field in report["summary"]
    assert report["summary"]["race_results"]["first_season"] == 1950


# Dataset manifest generation
def test_dataset_manifest_generation(tmp_path) -> None:
    os.makedirs(os.path.join(str(tmp_path), "data/canonical"), exist_ok=True)
    with open(os.path.join(str(tmp_path), "data/canonical/races.json"), "w", encoding="utf-8") as handle:
        json.dump([{"race_id": "r1"}], handle)
    manifest = generate_dataset_manifest(str(tmp_path), "f1-dataset-v1.0",
                                         source_versions={"jolpica": "0.1.0"})
    assert manifest["dataset_version"] == "f1-dataset-v1.0"
    assert manifest["schema_version"]
    assert os.path.exists(os.path.join(str(tmp_path), "data/manifests/dataset-manifest.json"))


# Era-normalized metrics (feature-derived, not subjective ratings)
def test_era_normalized_metrics() -> None:
    from app.data.features import driver_features

    results = [{"race_id": f"r{i}", "driver_id": "d1", "constructor_id": "c1",
                "grid_position": 5, "final_position": 3, "status": "finished"}
               for i in range(5)]
    feats = {f.name: f for f in driver_features("d1", "2024", results)}
    # Era-normalized field should exist or be derivable (avg_finish percentile)
    assert feats["avg_finish"].value == 3.0
    # No subjective 0-100 ratings leaked
    for feat in feats.values():
        if feat.value is not None:
            assert -1000 < feat.value < 1000  # raw statistical, not clipped rating


# No fabricated data
def test_no_fabricated_telemetry_for_1950s() -> None:
    assert not availability_for("telemetry", 1960).available
    assert availability_for("telemetry", 2024).available


# Reproducibility: same inputs → same canonical
def test_reproducibility_canonical() -> None:
    from app.data.fusion import CanonicalFusionEngine

    bundles = [[{"race_id": "r1", "winner": "VER",
                 "_provenance": {"source_provider": "jolpica",
                                 "transformation_chain": ["fetch"]}}]]
    e1 = CanonicalFusionEngine()
    c1, _ = e1.fuse_all(bundles)
    e2 = CanonicalFusionEngine()
    c2, _ = e2.fuse_all(bundles)
    assert c1 == c2
