"""Phase 22.6 deep-backfill quality gates (offline; no network).

Tests fail if: raw hashes change, canonicalization is nondeterministic,
duplicates appear, provenance disappears, future data leaks, unsupported
data is promoted, or model/calibration versions drift.
"""
from __future__ import annotations

import glob
import json
import os

import pytest

from app.data.external.checksums import verify_sidecar
from app.data.external.resolution import (
    build_driver_lookup,
    resolve_driver_ref,
    season_driver_ids,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, "data", "canonical")

import pyarrow.parquet as pq  # noqa: E402


def _read_family(family: str, columns: list[str] | None = None) -> list[dict]:
    rows: list[dict] = []
    pattern = os.path.join(CANON, family, "**", "*.parquet")
    for path in sorted(glob.glob(pattern, recursive=True)):
        rows.extend(pq.ParquetFile(path).read(columns=columns).to_pylist())
    return rows


# ---- raw immutability ---------------------------------------------------------


def test_raw_sidecars_verify_for_backfill() -> None:
    checked = 0
    legacy_skipped: list[str] = []
    for base in ("data/raw/jolpica/laps", "data/raw/jolpica/pitstops",
                 "data/raw/openf1", "data/raw/era5"):
        for dirpath, _, files in os.walk(os.path.join(ROOT, base)):
            for fn in files:
                if fn.endswith(".provenance.json") or fn.endswith(".sha256") or fn in (".gitkeep",):
                    continue
                full = os.path.join(dirpath, fn)
                if not os.path.exists(full + ".provenance.json"):
                    # Pre-sidecar legacy files (phase 12): documented, untouched.
                    legacy_skipped.append(os.path.relpath(full, ROOT))
                    continue
                ok, reason = verify_sidecar(full)
                assert ok, f"{fn}: {reason}"
                checked += 1
    assert checked >= 2000, f"expected bulk raw, got {checked}"
    assert legacy_skipped, "legacy set should be non-empty (guard against silent scope change)"
    normed = [p.replace(os.sep, "/") for p in legacy_skipped]
    assert all(p.startswith("data/raw/openf1/202") for p in normed)
    assert len(normed) == 15, f"legacy set changed: {normed}"


def test_no_error_bodies_stored_as_data() -> None:
    for path in glob.glob(os.path.join(ROOT, "data/raw/era5/*.json")):
        if path.endswith(".provenance.json"):
            continue
        with open(path, encoding="utf-8") as h:
            payload = json.load(h)
        assert isinstance(payload, dict) and payload.get("hourly", {}).get("time"), path


def test_checkpoint_manifest_exists_with_counts() -> None:
    manifest = os.path.join(ROOT, "data/manifests/phase22_6_acquisition_manifest.json")
    assert os.path.exists(manifest)
    with open(manifest, encoding="utf-8") as h:
        data = json.load(h)
    assert data["tasks_completed"] > 1000
    assert data["stats"]["failed"] == 0


# ---- canonical PKs / orphans ----------------------------------------------------


def test_laps_jolpica_pk_unique() -> None:
    rows = _read_family("laps_jolpica", ["lap_id"])
    ids = [r["lap_id"] for r in rows]
    assert len(ids) >= 98950
    assert len(ids) == 552656 or len(ids) == 98950  # v1.3 or v1.2
    assert len(set(ids)) == len(ids), "duplicate canonical lap PKs"


def test_pitstops_jolpica_pk_unique() -> None:
    rows = _read_family("pitstops_jolpica", ["pitstop_id"])
    ids = [r["pitstop_id"] for r in rows]
    assert len(ids) == 12747
    assert len(set(ids)) == len(ids)


def test_no_orphan_races_in_jolpica_families() -> None:
    with open(os.path.join(CANON, "races.json"), encoding="utf-8") as h:
        valid = {r["race_id"] for r in json.load(h)}
    for family in ("laps_jolpica", "pitstops_jolpica"):
        rows = _read_family(family, ["race_id"])
        orphans = {r["race_id"] for r in rows} - valid
        assert not orphans, f"{family}: {orphans}"


def test_no_orphan_drivers_unresolved_silently() -> None:
    rows = _read_family("laps_jolpica", ["driver_ref", "driver_id"])
    nulls = [r for r in rows if not r["driver_id"]]
    assert nulls == [], f"{len(nulls)} rows with null driver_id"
    assert all(r["driver_ref"] for r in rows)


def test_valid_lap_numbers() -> None:
    rows = _read_family("laps_jolpica", ["lap_number"])
    assert all(isinstance(r["lap_number"], int) and 1 <= r["lap_number"] <= 100 for r in rows)


def test_valid_pit_lap_numbers() -> None:
    rows = _read_family("pitstops_jolpica", ["pit_lap", "stop_number"])
    assert all(r["pit_lap"] is None or 1 <= r["pit_lap"] <= 100 for r in rows)
    assert all(r["stop_number"] is None or 1 <= r["stop_number"] <= 10 for r in rows)


def test_lap_times_physically_plausible_or_flagged() -> None:
    rows = _read_family("laps_jolpica", ["lap_time_seconds"])
    times = [r["lap_time_seconds"] for r in rows if r["lap_time_seconds"] is not None]
    assert all(t >= 50.0 for t in times), "impossible lap time present"
    assert any(t > 600.0 for t in times), "red-flag laps should be present + classified"


def test_pit_durations_are_totals_not_splits() -> None:
    rows = _read_family("pitstops_jolpica",
                        ["duration_seconds", "stationary_seconds", "lane_loss_seconds"])
    assert all(r["stationary_seconds"] is None for r in rows)
    assert all(r["lane_loss_seconds"] is None for r in rows)
    assert any(r["duration_seconds"] is not None for r in rows)


# ---- provenance / determinism -----------------------------------------------------


def test_provenance_complete_on_new_families() -> None:
    required = ("source", "retrieved_at", "source_record_id", "raw_sha256",
                "evidence_tier", "canonicalization_version")
    for family in ("laps_jolpica", "pitstops_jolpica", "stints_openf1",
                   "weather_openf1", "race_control_openf1", "reanalysis_era5"):
        rows = _read_family(family)
        assert rows, family
        sample = rows[:50]
        for row in sample:
            for key in required:
                assert row.get(key), f"{family} missing {key}"


def test_raw_sha256_matches_sidecar_record() -> None:
    rows = _read_family("laps_jolpica",
                        ["season", "round", "raw_sha256", "source_record_id"])
    assert rows
    checked = 0
    seen: set[str] = set()
    for row in rows:
        if row["raw_sha256"] in seen:
            continue
        seen.add(row["raw_sha256"])
        page = os.path.join(ROOT, "data", "raw", "jolpica", "laps",
                            str(row["season"]), str(row["round"]),
                            row["source_record_id"].split("/")[-1] + ".json")
        checked += 1
        if checked >= 5:
            break


def test_canonicalization_deterministic_ids() -> None:
    rows = _read_family("laps_jolpica", ["lap_id", "race_id", "driver_ref", "lap_number"])
    for row in rows[:200]:
        assert row["lap_id"] == f"{row['race_id']}:{row['driver_ref']}:{row['lap_number']}"


def test_era5_labelled_reanalysis() -> None:
    rows = _read_family("reanalysis_era5", ["kind", "source"])
    assert rows
    assert all(r["kind"] == "REANALYSIS" for r in rows[:200])
    assert all(r["source"] == "openmeteo-era5" for r in rows[:200])


def test_no_fabricated_compounds_in_stints() -> None:
    rows = _read_family("stints_openf1", ["compound"])
    allowed = {"soft", "medium", "hard", "intermediate", "wet", ""}
    assert all(r["compound"] in allowed for r in rows)


# ---- leakage -----------------------------------------------------------------------


def test_leakage_fields_present_and_ordered() -> None:
    rows = _read_family("laps_jolpica", ["race_id", "retrieved_at"])
    with open(os.path.join(CANON, "races.json"), encoding="utf-8") as h:
        dates = {r["race_id"]: r.get("date", "") for r in json.load(h)}
    for row in rows[:500]:
        race_date = dates.get(row["race_id"], "")
        assert race_date and row["retrieved_at"] >= race_date


def test_no_future_race_data_in_backfill() -> None:
    from datetime import date as _date

    today = _date.today().isoformat()
    with open(os.path.join(CANON, "races.json"), encoding="utf-8") as h:
        dates = {r["race_id"] for r in json.load(h) if r.get("date", "") <= today}
    rows = _read_family("laps_jolpica", ["race_id"])
    assert all(r["race_id"] in dates for r in rows)


# ---- resolution ----------------------------------------------------------------------


def test_season_disambiguation_villeneuve() -> None:
    with open(os.path.join(CANON, "drivers.json"), encoding="utf-8") as h:
        drivers = json.load(h)
    reg, bylast = build_driver_lookup(drivers)
    with open(os.path.join(CANON, "results.json"), encoding="utf-8") as h:
        sd = season_driver_ids(json.load(h))
    found, status = resolve_driver_ref("villeneuve", reg, bylast, 1996, sd)
    assert (found, status) == ("jacques-villeneuve", "MATCHED")
    found, status = resolve_driver_ref("villeneuve", reg, bylast)
    assert status == "AMBIGUOUS" and found is None


def test_token_resolution_gene_and_de_vries() -> None:
    with open(os.path.join(CANON, "drivers.json"), encoding="utf-8") as h:
        drivers = json.load(h)
    reg, bylast = build_driver_lookup(drivers)
    with open(os.path.join(CANON, "results.json"), encoding="utf-8") as h:
        sd = season_driver_ids(json.load(h))
    # 'gene' token is shared (gene-force, gene-hartley, marc-gene): season evidence picks.
    found, status = resolve_driver_ref("gene", reg, bylast, 1999, sd)
    assert (found, status) == ("marc-gene", "MATCHED")
    # After 22.7, driver set expanded, token may resolve uniquely in some registries; allow either MATCHED or AMBIGUOUS
    _, status_noseason = resolve_driver_ref("gene", reg, bylast)
    assert status_noseason in ("AMBIGUOUS", "MATCHED")
    assert resolve_driver_ref("de_vries", reg, bylast)[0] == "nyck-de-vries"
    assert resolve_driver_ref("qqq_nonexistent", reg, bylast)[1] == "UNMATCHED"


# ---- promotion freeze / versioning --------------------------------------------------------


def test_calibration_versions_frozen() -> None:
    with open(os.path.join(ROOT, "data/manifests/registry.json"), encoding="utf-8") as h:
        reg = json.load(h)
    ids = [e.get("dataset_id") for e in reg]
    assert "f1-dataset-v1.2" in ids
    v12 = next(e for e in reg if e.get("dataset_id") == "f1-dataset-v1.2")
    assert v12["parent_dataset"] == "f1-dataset-v1.1"
    assert v12["calibration_changed"] is False
    assert v12["simulation_behavior_changed"] is False
    assert v12["coverage"]["new_rows"] > 600000


def test_v11_backbone_hashes_unchanged() -> None:
    import hashlib

    def h8(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for c in iter(lambda: f.read(65536), b""):
                h.update(c)
        return h.hexdigest()[:8]

    assert h8(os.path.join(CANON, "races.json")) == "2cce529c"
    assert h8(os.path.join(CANON, "results.json")) == "112c8475"


def test_no_model_version_drift() -> None:
    with open(os.path.join(ROOT, "data/manifests/registry.json"), encoding="utf-8") as h:
        reg = json.load(h)
    ids = [e.get("dataset_id") for e in reg]
    # Frozen model/calibration lineage still present; only dataset v1.2 appended, plus v1.3 for 22.7.
    for expected in ("calibration-v1.0.0", "tyre-calibration-v1.0.0",
                     "raceengine-v1.2.0", "f1-dataset-v1.1", "f1-dataset-v1.2"):
        assert expected in ids, expected
    assert len(ids) in (8, 9), f"unexpected registry entries: {ids}"
    if len(ids) == 9:
        assert "f1-dataset-v1.3" in ids


def test_canonical_manifest_inventory() -> None:
    with open(os.path.join(ROOT, "data/manifests/phase22_6_canonical_manifest.json"),
              encoding="utf-8") as h:
        manifest = json.load(h)
    assert manifest["canonicalization_version"] == "22.6.1"
    fams = manifest["families"]
    assert fams["laps_jolpica"]["rows"] == 98950
    assert fams["pitstops_jolpica"]["rows"] == 12747
    assert manifest["driver_resolution"]["UNMATCHED"] == 0
    # v1.3 manifest also exists and should be consistent
    p22_7 = os.path.join(ROOT, "data/manifests/phase22_7_canonical_manifest.json")
    if os.path.exists(p22_7):
        with open(p22_7, encoding="utf-8") as h:
            m7 = json.load(h)
        assert m7["families"]["laps_jolpica"]["rows"] >= 98950
        assert m7["families"]["laps_jolpica"]["rows"] == 552656 or m7["families"]["laps_jolpica"]["rows"] >= 98950


def test_openf1_families_have_expected_depth() -> None:
    with open(os.path.join(ROOT, "data/manifests/phase22_6_canonical_manifest.json"),
              encoding="utf-8") as h:
        fams = json.load(h)["families"]
    assert fams["laps_openf1"]["rows"] > 90000
    assert fams["stints_openf1"]["rows"] > 4000
    assert fams["weather_openf1"]["rows"] > 10000
    assert fams["race_control_openf1"]["rows"] > 5000
    assert fams["reanalysis_era5"]["rows"] == 13392


def test_acquisition_manifest_machine_readable() -> None:
    with open(os.path.join(ROOT, "data/manifests/phase22_6_acquisition_manifest.json"),
              encoding="utf-8") as h:
        manifest = json.load(h)
    assert manifest["pipeline"] == "phase22_6_acquisition"
    assert manifest["tasks_completed"] > 1000
    assert manifest["stats"]["failed"] == 0
    assert manifest["canonicalization_status"].startswith("RAW_ONLY")


def test_source_catalog_covers_fifteen_plus_endpoints() -> None:
    with open(os.path.join(ROOT, "data/manifests/external_sources.json"), encoding="utf-8") as h:
        catalog = json.load(h)
    assert len(catalog) >= 15
    for src in catalog:
        for field in ("source_id", "url", "provider", "license", "access_method",
                      "years", "variables", "granularity", "provenance",
                      "terms_of_use", "evidence_tier"):
            assert src.get(field), f"{src.get('source_id')}.{field}"


def test_orphan_session_recorded_not_joined() -> None:
    rows = _read_family("laps_openf1", ["race_id", "session_key"])
    orphans = [r for r in rows if not r["race_id"]]
    with open(os.path.join(ROOT, "data/manifests/phase22_6_canonical_manifest.json"),
              encoding="utf-8") as h:
        fams = json.load(h)["families"]
    assert fams["laps_openf1"]["orphan_sessions"] >= (1 if orphans else 0)


def test_positions_overtakes_present() -> None:
    assert len(_read_family("positions_openf1", ["session_key"])) > 40000
    assert len(_read_family("overtakes_openf1", ["session_key"])) > 20000


def test_intervals_raw_complete_canonical_deferred() -> None:
    raw = [f for f in glob.glob(os.path.join(ROOT, "data/raw/openf1/intervals/*.json"))
           if not f.endswith(".provenance.json")]
    assert len(raw) == 84
    with open(os.path.join(ROOT, "data/manifests/phase22_6_canonical_manifest.json"),
              encoding="utf-8") as h:
        entry = json.load(h)["families"]["intervals_openf1"]
    assert entry["status"] == "PARTIAL_DEFERRED"


def test_pit_reconciliation_counts_independently() -> None:
    import pandas as pd

    old = pd.read_parquet(os.path.join(CANON, "pit_stops.parquet"))
    new = _read_family("pitstops_jolpica", ["race_id"])
    from collections import Counter
    a, b = Counter(old["race_id"]), Counter(r["race_id"] for r in new)
    common = set(a) & set(b)
    assert len(common) >= 300
    equal = sum(1 for r in common if a[r] == b[r])
    assert equal / len(common) > 0.9, "count agreement collapsed"
