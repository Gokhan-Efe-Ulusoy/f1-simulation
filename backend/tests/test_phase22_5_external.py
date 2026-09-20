"""Phase 22.5 external-data acquisition tests (offline; no network).

Covers: manifest validity, checksums, raw immutability, normalization,
entity resolution, deduplication, conflicts, provenance, temporal ordering,
leakage fields, promotion gates, canonical compatibility, version lineage.
"""
from __future__ import annotations

import json
import os

import pytest

from app.data.external.base import QUALITY_CRITERIA, EvidenceTier
from app.data.external.catalog import build_default_catalog
from app.data.external.checksums import sha256_bytes, verify_sidecar, write_sidecar
from app.data.external.conflicts import (
    ConflictRecord,
    classify_numeric_diff,
    conflict_pattern,
    detect_lap_conflicts,
)
from app.data.external.coverage import (
    BASELINE_TIERS,
    build_coverage_matrix,
    build_readiness,
    era_for_season,
)
from app.data.external.deduplication import deduplicate, row_identity
from app.data.external.download import RateLimiter, download_to_raw
from app.data.external.license import gate_for, may_acquire
from app.data.external.normalization import (
    normalize_jolpica_laps,
    normalize_jolpica_pitstops,
    normalize_openf1_race_control,
    normalize_openf1_stints,
    normalize_openf1_weather,
    normalize_openmeteo_hourly,
)
from app.data.external.promotion import assess_promotion
from app.data.external.resolution import (
    AliasRegistry,
    resolve_with_aliases,
    summarize_resolutions,
)
from app.data.regulations.schema import REGULATION_CATEGORIES, seed_evidence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFESTS = os.path.join(ROOT, "data", "manifests")
REQUIRED_SOURCE_FIELDS = (
    "source_id", "source_name", "url", "provider", "license", "access_method",
    "years", "races", "sessions", "variables", "granularity", "format",
    "provenance", "update_frequency", "known_limitations", "terms_of_use",
    "evidence_tier",
)


# ---- catalog / manifests ----------------------------------------------------


def test_catalog_has_fifteen_sources_with_required_fields() -> None:
    catalog = build_default_catalog()
    assert len(catalog) == 15
    for src in catalog:
        for field in REQUIRED_SOURCE_FIELDS:
            assert getattr(src, field, None) not in (None, ""), f"{src.source_id}.{field}"
        assert src.evidence_tier in [t.value for t in EvidenceTier]
        assert set(src.quality.model_dump()) == set(QUALITY_CRITERIA)


def test_external_sources_manifest_matches_catalog() -> None:
    path = os.path.join(MANIFESTS, "external_sources.json")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as h:
        manifest = json.load(h)
    assert len(manifest) == len(build_default_catalog()) == 15
    ids = {s["source_id"] for s in manifest}
    assert {"jolpica-laps", "openf1-timing", "openmeteo-era5", "f1db-database"} <= ids


def test_acquisition_manifest_pins_versions_and_flags() -> None:
    path = os.path.join(MANIFESTS, "external_acquisition_manifest.json")
    with open(path, encoding="utf-8") as h:
        manifest = json.load(h)
    assert manifest["canonical_version"].startswith("f1-dataset-v1.1")
    assert manifest["calibration_version"].startswith("calibration-v1.0.0")
    assert manifest["simulation_behavior_changed"] is False
    assert manifest["counts"]["laps_jolpica"] == 1129
    assert manifest["openf1_session_key"] == 9472
    assert len(manifest["raw_files"]) >= 30
    assert manifest["promotion_gate"], "gate must assess variables"


def test_conflicts_manifest_schema_and_pattern() -> None:
    path = os.path.join(MANIFESTS, "external_conflicts.json")
    with open(path, encoding="utf-8") as h:
        manifest = json.load(h)
    assert manifest["compared_pairs"] == 1129
    assert len(manifest["conflicts"]) == 20
    assert manifest["pattern"]["pattern"] == "systematic_single_lap_offset"
    for conflict in manifest["conflicts"]:
        assert conflict["classification"] == "genuine_conflict"
        assert conflict["source_a"] == "jolpica-laps"


def test_coverage_manifest_tracks_all_variables() -> None:
    path = os.path.join(MANIFESTS, "external_coverage.json")
    with open(path, encoding="utf-8") as h:
        manifest = json.load(h)
    variables = {row["variable"] for row in manifest["matrix"]}
    assert set(BASELINE_TIERS) <= variables
    assert manifest["canonical_version"].startswith("f1-dataset-v1.1")


# ---- checksums / raw immutability -------------------------------------------


def test_sha256_known_vector() -> None:
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_sidecar_write_and_verify(tmp_path) -> None:
    target = tmp_path / "payload.json"
    target.write_bytes(b'{"a": 1}')
    meta = write_sidecar(str(target), source_id="s", source_url="u",
                         license="l", download_timestamp="2026-09-19T00:00:00+00:00")
    assert meta["sha256"] == sha256_bytes(b'{"a": 1}')
    ok, reason = verify_sidecar(str(target))
    assert ok, reason


def test_sidecar_detects_tampering(tmp_path) -> None:
    target = tmp_path / "payload.json"
    target.write_bytes(b'{"a": 1}')
    write_sidecar(str(target), source_id="s", source_url="u",
                  license="l", download_timestamp="t")
    target.write_bytes(b'{"a": 2}')  # raw modified in place: must be caught
    ok, reason = verify_sidecar(str(target))
    assert not ok and "mismatch" in reason


def test_sidecar_missing_reports_false(tmp_path) -> None:
    target = tmp_path / "payload.json"
    target.write_bytes(b"x")
    ok, _ = verify_sidecar(str(target))
    assert not ok


def test_real_raw_sidecar_verifies() -> None:
    checked = 0
    for dirpath, _, files in os.walk(os.path.join(ROOT, "data", "raw", "external")):
        for fn in files:
            if fn.endswith(".provenance.json") or fn in (".gitkeep", ".gitignore"):
                continue
            ok, reason = verify_sidecar(os.path.join(dirpath, fn))
            assert ok, f"{fn}: {reason}"
            checked += 1
    assert checked >= 30, "all shipped raw files must verify"


# ---- downloader --------------------------------------------------------------


def test_download_writes_raw_and_sidecar(tmp_path) -> None:
    calls: list[str] = []

    def transport(url: str) -> bytes:
        calls.append(url)
        return b'{"hello": 1}'

    meta = download_to_raw(source_id="demo", url="https://example/x.json",
                           filename="x.json", raw_root=str(tmp_path),
                           license="l", transport=transport,
                           limiter=RateLimiter(min_interval_seconds=0))
    assert meta["sha256"] == sha256_bytes(b'{"hello": 1}')
    assert os.path.exists(os.path.join(str(tmp_path), "demo", "x.json"))


def test_download_reuses_valid_raw_without_network(tmp_path) -> None:
    calls: list[str] = []

    def transport(url: str) -> bytes:
        calls.append(url)
        return b"data"

    kwargs: dict = {"source_id": "demo", "url": "https://example/x",
                    "filename": "x.bin", "raw_root": str(tmp_path),
                    "license": "l", "limiter": RateLimiter(min_interval_seconds=0)}
    download_to_raw(transport=transport, **kwargs)
    download_to_raw(transport=transport, **kwargs)  # second call must not hit network
    assert len(calls) == 1


def test_download_retries_then_raises(tmp_path) -> None:
    def failing(_url: str) -> bytes:
        raise ConnectionError("down")

    with pytest.raises(RuntimeError, match="download failed"):
        download_to_raw(source_id="d", url="u", filename="f", raw_root=str(tmp_path),
                        license="l", transport=failing,
                        limiter=RateLimiter(min_interval_seconds=0))


# ---- license gates ------------------------------------------------------------


def test_acquirable_sources_allowed() -> None:
    for source_id in ("jolpica-laps", "jolpica-pitstops", "openf1-timing",
                      "openf1-pit", "openf1-stints", "openf1-weather",
                      "openf1-racecontrol", "fastf1-timing", "f1db-database",
                      "openmeteo-era5"):
        assert may_acquire(source_id), source_id


def test_restricted_sources_denied() -> None:
    assert not may_acquire("ergast-mirror-kaggle")
    assert not may_acquire("fia-documents")
    assert not may_acquire("official-f1-timing")
    assert not may_acquire("no-such-source")
    assert gate_for("f1db-database").attribution_required is True


# ---- normalization -------------------------------------------------------------


def _laps_page() -> dict:
    return {"MRData": {"RaceTable": {"Races": [{
        "date": "2024-03-02",
        "Laps": [{"number": "1", "Timings": [
            {"driverId": "max_verstappen", "time": "1:37.284", "position": "1"}]}]}]}}}


def test_normalize_jolpica_laps_golden() -> None:
    rows, warnings = normalize_jolpica_laps(_laps_page(), source_file="f.json",
                                            season=2024, round_no=1)
    assert warnings == []
    assert len(rows) == 1
    assert rows[0]["lap_time_seconds"] == pytest.approx(97.284)
    assert rows[0]["provenance"]["source_id"] == "jolpica-laps"
    assert rows[0]["provenance"]["observed_at"] == "2024-03-02"
    assert rows[0]["provenance"]["ingested_at"] != ""


def test_normalize_jolpica_laps_malformed_shape() -> None:
    rows, warnings = normalize_jolpica_laps({"MRData": {}}, source_file="f.json",
                                            season=2024, round_no=1)
    assert rows == [] and warnings, "malformed payload must warn, never fabricate"


def test_normalize_jolpica_pit_durations() -> None:
    payload = {"MRData": {"RaceTable": {"Races": [{
        "date": "2024-03-02",
        "PitStops": [
            {"driverId": "a", "lap": "10", "stop": "1", "time": "15:00:00", "duration": "24.418"},
            {"driverId": "b", "lap": "11", "stop": "1", "time": "15:01:00", "duration": "1:14.773"},
            {"driverId": "c", "lap": "12", "stop": "1", "time": "15:02:00", "duration": "26:15.603"},
            {"driverId": "d", "lap": "13", "stop": "1", "time": "15:03:00", "duration": "??"},
        ]}]}}}
    rows, warnings = normalize_jolpica_pitstops(payload, source_file="f.json",
                                                season=2024, round_no=1)
    assert rows[0]["total_pit_loss_seconds"] == pytest.approx(24.418)
    assert rows[1]["total_pit_loss_seconds"] == pytest.approx(74.773)
    assert rows[2]["total_pit_loss_seconds"] == pytest.approx(1575.603)
    assert rows[3]["total_pit_loss_seconds"] is None
    assert rows[0]["stationary_time_seconds"] is None  # split not in source
    assert len(warnings) == 1


def test_normalize_openf1_stints_compounds() -> None:
    rows, warnings = normalize_openf1_stints([
        {"session_key": 1, "meeting_key": 2, "driver_number": 4,
         "stint_number": 1, "compound": "SOFT", "lap_start": 1,
         "lap_end": 15, "tyre_age_at_start": 0},
        {"session_key": 1, "meeting_key": 2, "driver_number": 4,
         "stint_number": 2, "compound": "SUPER", "lap_start": 16,
         "lap_end": 30, "tyre_age_at_start": 1},
    ], source_file="s.json")
    assert rows[0]["compound"] == "soft"
    assert rows[1]["compound"] == ""  # unknown compound never invented
    assert len(warnings) == 1


def test_normalize_openf1_weather_and_race_control() -> None:
    wrows, _ = normalize_openf1_weather(
        [{"session_key": 9, "meeting_key": 1, "date": "2024-03-02T15:00:00+00:00",
          "air_temperature": 28.5, "track_temperature": 35.0, "humidity": 20.0,
          "pressure": 1010.0, "rainfall": 0, "wind_speed": 2.5, "wind_direction": 180}],
        source_file="w.json")
    assert wrows[0]["air_temperature_c"] == 28.5
    assert wrows[0]["provenance"]["observed_at"].startswith("2024-03-02")
    rrows, _ = normalize_openf1_race_control(
        [{"session_key": 9, "meeting_key": 1, "date": "d", "category": "Flag",
          "flag": None, "lap_number": 3, "sector": None, "message": "YELLOW",
          "scope": None, "driver_number": None}], source_file="r.json")
    assert rrows[0]["flag"] == "" and rrows[0]["message"] == "YELLOW"


def test_normalize_openmeteo_marks_reanalysis() -> None:
    payload = {"latitude": 26.0, "longitude": 50.5, "elevation": 13.0,
               "hourly": {"time": ["2024-03-02T00:00", "2024-03-02T01:00"],
                          "temperature_2m": [22.0, 21.5], "relative_humidity_2m": [40, 41],
                          "precipitation": [0.0, 0.0], "pressure_msl": [1012, 1012],
                          "wind_speed_10m": [10, 11], "wind_direction_10m": [300, 301]}}
    rows, warnings = normalize_openmeteo_hourly(payload, source_file="r.json",
                                                latitude=26.03, longitude=50.51,
                                                race_id="2024-bahrain")
    assert warnings == [] and len(rows) == 2
    assert all(r["kind"] == "REANALYSIS" for r in rows)
    empty, warns = normalize_openmeteo_hourly({"hourly": {"time": []}},
                                              source_file="e.json", latitude=0,
                                              longitude=0, race_id="x")
    assert empty == [] and warns


# ---- deduplication -------------------------------------------------------------


def test_deduplicate_detects_repeats() -> None:
    rows = [
        {"season": 2024, "round": 1, "driver_ref": "a", "lap_number": 1},
        {"season": 2024, "round": 1, "driver_ref": "a", "lap_number": 1},
        {"season": 2024, "round": 1, "driver_ref": "a", "lap_number": 2},
    ]
    result = deduplicate(rows, "laps")
    assert result["new_rows"] == 2 and result["duplicate_rows"] == 1


def test_deduplicate_flags_invalid_laps() -> None:
    rows = [{"season": 2024, "round": 1, "driver_ref": "a", "lap_number": None}]
    result = deduplicate(rows, "laps")
    assert result["invalid_rows"] == 1 and result["new_rows"] == 0


def test_row_identity_deterministic_across_key_styles() -> None:
    jolpica = {"season": 2024, "round": 1, "driver_ref": "max_verstappen", "lap_number": 5}
    openf1 = {"session_key": 9472, "driver_number": 1, "lap_number": 5}
    assert row_identity(jolpica, "laps") == row_identity(jolpica, "laps")
    assert row_identity(jolpica, "laps") != row_identity(openf1, "laps")


def test_known_identities_count_as_duplicates() -> None:
    rows = [{"season": 2024, "round": 1, "driver_ref": "a", "lap_number": 1}]
    known = {row_identity(rows[0], "laps")}
    result = deduplicate(rows, "laps", known_identities=known)
    assert result["duplicate_rows"] == 1 and result["new_rows"] == 0


# ---- conflicts -------------------------------------------------------------------


def test_numeric_diff_rounding_band() -> None:
    cls, diff = classify_numeric_diff(92.381, 92.382)
    assert cls == "rounding" and diff == pytest.approx(0.001)


def test_numeric_diff_genuine() -> None:
    cls, diff = classify_numeric_diff(97.284, 97.759)
    assert cls == "genuine_conflict" and diff == pytest.approx(0.475)


def test_lap_conflicts_require_driver_map() -> None:
    jolpica = [{"season": 2024, "round": 1, "driver_ref": "max_verstappen",
                "lap_number": 1, "lap_time_seconds": 97.284}]
    openf1 = [{"session_key": 9472, "driver_number": 1, "lap_number": 1,
               "lap_time_seconds": 97.759}]
    assert detect_lap_conflicts(jolpica, openf1, season=2024, round_no=1,
                                driver_map={}) == []  # unmapped: skip, never guess
    found = detect_lap_conflicts(jolpica, openf1, season=2024, round_no=1,
                                 driver_map={"1": "max_verstappen"})
    assert len(found) == 1 and isinstance(found[0], ConflictRecord)


def test_conflict_pattern_systematic_and_empty() -> None:
    assert conflict_pattern([])["pattern"] == "no_conflicts"
    recs = [ConflictRecord(entity=f"laps|2024|1|d{i}|1", variable="lap_time_seconds",
                           source_a="j", value_a=90.0, source_b="o",
                           value_b=90.4, abs_diff=0.4,
                           classification="genuine_conflict") for i in range(3)]
    pattern = conflict_pattern(recs)
    assert pattern["pattern"] == "systematic_single_lap_offset"
    assert pattern["direction"] == "B_slower"


# ---- entity resolution -------------------------------------------------------------


def test_resolution_matched() -> None:
    registry = AliasRegistry()
    registry.register_entity("max-verstappen", ["Max Verstappen", "VER"])
    out = resolve_with_aliases("VER", [registry])
    assert out["status"] == "MATCHED" and out["canonical_id"] == "max-verstappen"


def test_resolution_ambiguous_never_merges() -> None:
    first, second = AliasRegistry(), AliasRegistry()
    first.register_entity("team-a", ["Speed"])
    second.register_entity("team-b", ["Speed"])
    out = resolve_with_aliases("Speed", [first, second])
    assert out["status"] == "AMBIGUOUS" and out["canonical_id"] is None
    assert sorted(out["candidates"]) == ["team-a", "team-b"]


def test_resolution_unmatched() -> None:
    out = resolve_with_aliases("Nobody", [AliasRegistry()])
    assert out["status"] == "UNMATCHED"


def test_summarize_resolutions_counts() -> None:
    summary = summarize_resolutions([{"status": "MATCHED"}, {"status": "AMBIGUOUS"},
                                     {"status": "UNMATCHED"}, {"status": "MATCHED"}])
    assert summary == {"MATCHED": 2, "AMBIGUOUS": 1, "UNMATCHED": 1}


# ---- promotion gate ---------------------------------------------------------------


def test_gate_refuses_without_observations() -> None:
    verdict = assess_promotion(variable="telemetry", current_status="LIMITED",
                               new_observations=0, eras_observed=[],
                               eras_claimed=["2022-2026"], source_ids=[],
                               conflicts=0, compared=0, missingness=1.0,
                               temporal_resolution="3.7 Hz", min_observations=1000)
    assert verdict.promotion_candidate is False
    assert verdict.promoted_tier == "LIMITED"  # tier never fabricated upward


def test_gate_refuses_high_conflict_rate() -> None:
    verdict = assess_promotion(variable="lap_timing", current_status="LIMITED",
                               new_observations=500, eras_observed=["2022-2026"],
                               eras_claimed=["2022-2026"], source_ids=["s"],
                               conflicts=60, compared=500, missingness=0.0,
                               temporal_resolution="lap", min_observations=100)
    assert verdict.promotion_candidate is False and "conflict" in verdict.reason


def test_gate_era_scoped_candidate() -> None:
    verdict = assess_promotion(variable="tyre_age", current_status="PRIOR_ONLY",
                               new_observations=63, eras_observed=["2022-2026"],
                               eras_claimed=["2022-2026"], source_ids=["openf1-stints"],
                               conflicts=0, compared=63, missingness=0.05,
                               temporal_resolution="stint", min_observations=20)
    assert verdict.promotion_candidate is True
    assert verdict.promoted_tier == "LIMITED"


def test_gate_never_relabels_unobserved_eras() -> None:
    verdict = assess_promotion(variable="lap_timing", current_status="LIMITED",
                               new_observations=2258, eras_observed=["2022-2026"],
                               eras_claimed=["2022-2026", "1950-1969"],
                               source_ids=["jolpica-laps"], conflicts=20,
                               compared=1129, missingness=0.02,
                               temporal_resolution="lap", min_observations=100)
    assert verdict.promotion_candidate is True
    assert "1950-1969" in verdict.reason and "NOT observed" in verdict.coverage_delta


# ---- coverage / readiness / regulations ----------------------------------------------


def test_coverage_matrix_claims_nothing_without_observations() -> None:
    matrix = build_coverage_matrix({}, {}, canonical_changed=False)
    assert len(matrix) == len(BASELINE_TIERS)
    for row in matrix:
        assert row["acquired"] == 0 and "no change" in row["coverage_change"]


def test_era_boundaries() -> None:
    assert era_for_season(1950) == "1950-1969"
    assert era_for_season(2007) == "2000-2009"
    assert era_for_season(2024) == "2022-2026"


def test_readiness_records_sorted_with_tiers() -> None:
    readiness = build_readiness({
        "b_var": {"sample_size": 1, "years": "2024", "circuits": 1, "drivers": 2,
                  "observations": 1, "confounders": ["c"], "candidate_model": "m",
                  "evidence_tier": "LIMITED"},
        "a_var": {"sample_size": 0, "years": "", "circuits": 0, "drivers": 0,
                  "observations": 0, "confounders": [], "candidate_model": "none",
                  "evidence_tier": "PRIOR_ONLY"},
    })
    assert [c.variable for c in readiness] == ["a_var", "b_var"]
    assert readiness[0].evidence_tier == "PRIOR_ONLY"


def test_regulation_evidence_layer_valid() -> None:
    assert set(REGULATION_CATEGORIES) >= {"DRS_ALLOWED", "POINTS_SYSTEM", "SPRINT_FORMAT"}
    seed = seed_evidence()
    assert len(seed) > 300
    for row in seed:
        assert 1950 <= row["season"] <= 2026
        assert row["regulation_category"] in REGULATION_CATEGORIES
        assert 0.0 <= row["confidence"] <= 1.0
        assert row["source"] != ""
    path = os.path.join(ROOT, "data", "regulations", "regulation_evidence.json")
    with open(path, encoding="utf-8") as h:
        stored = json.load(h)
    assert len(stored) == len(seed)


# ---- provenance / leakage / compatibility ----------------------------------------------


def test_staging_rows_preserve_provenance_and_leakage_fields() -> None:
    staging = os.path.join(ROOT, "data", "external_staging", "laps_jolpica.json")
    with open(staging, encoding="utf-8") as h:
        rows = json.load(h)
    assert len(rows) == 1129
    for row in rows[:25]:
        prov = row["provenance"]
        for key in ("source_id", "source_file", "source_record_id",
                    "observed_at", "ingested_at"):
            assert prov.get(key), f"missing {key}"
        assert prov["observed_at"] < prov["ingested_at"], "observation must predate ingestion"


def test_reanalysis_timestamps_temporally_ordered_per_race() -> None:
    staging = os.path.join(ROOT, "data", "external_staging", "reanalysis_openmeteo.json")
    with open(staging, encoding="utf-8") as h:
        rows = json.load(h)
    by_race: dict[str, list[str]] = {}
    for row in rows:
        by_race.setdefault(row["race_id"], []).append(row["timestamp"])
    assert len(by_race) == 6
    for stamps in by_race.values():
        assert stamps == sorted(stamps)


def test_staging_drivers_resolve_to_canonical() -> None:
    from app.data.external.resolution import build_driver_registry

    with open(os.path.join(ROOT, "data", "canonical", "drivers.json"), encoding="utf-8") as h:
        registry = build_driver_registry(json.load(h))
    with open(os.path.join(ROOT, "data", "external_staging", "laps_jolpica.json"),
              encoding="utf-8") as h:
        rows = json.load(h)
    refs = {r["driver_ref"].replace("_", "-") for r in rows}
    assert len(refs) == 20
    for ref in refs:
        assert registry.resolve(ref) is not None, f"unresolved {ref}"
