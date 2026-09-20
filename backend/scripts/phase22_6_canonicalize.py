"""Phase 22.6 canonicalization: raw -> provenance-bearing parquet families.

Idempotent: verified partitions are skipped. Bounded memory: one race/
session at a time. Deterministic IDs, no invented values (nulls + warnings).

Families:
  canonical/laps_jolpica/season=<y>/round=<r>/part-000.parquet
  canonical/pitstops_jolpica/season=<y>/round=<r>/part-000.parquet
  canonical/laps_openf1/season=<y>/session=<k>/part-000.parquet
  canonical/stints_openf1, weather_openf1, pitstops_openf1,
  race_control_openf1, positions_openf1, overtakes_openf1,
  teamradio_openf1, results_openf1, intervals_openf1 (same layout)
  canonical/reanalysis_era5/race=<race_id>/part-000.parquet
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from app.data.external.checksums import sha256_file  # noqa: E402
from app.data.external.normalization import (  # noqa: E402
    normalize_jolpica_laps,
    normalize_jolpica_pitstops,
    normalize_openf1_laps,
    normalize_openf1_pit,
    normalize_openf1_race_control,
    normalize_openf1_stints,
    normalize_openf1_weather,
)
from app.data.external.resolution import (  # noqa: E402
    build_driver_lookup,
    resolve_driver_ref,
    season_driver_ids,
)
from app.data.normalization import normalize_duration_seconds, normalize_int  # noqa: E402
from app.data.provenance import utc_now_iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, "data", "canonical")
RAW_JOLPICA = os.path.join(ROOT, "data", "raw", "jolpica")
RAW_OPENF1 = os.path.join(ROOT, "data", "raw", "openf1")
RAW_ERA5 = os.path.join(ROOT, "data", "raw", "era5")
CANON_MANIFEST = os.path.join(ROOT, "data", "manifests", "phase22_6_canonical_manifest.json")
CANON_VERSION = "22.6.1"


def race_map() -> dict[tuple[int, int], dict]:
    """(season, round) -> canonical race row."""
    with open(os.path.join(CANON, "races.json"), encoding="utf-8") as h:
        races = json.load(h)
    return {(int(r["season_id"]), int(r["round"])): r for r in races}


def date_to_race() -> dict[str, dict]:
    """race date -> canonical race row (for OpenF1 session joins)."""
    with open(os.path.join(CANON, "races.json"), encoding="utf-8") as h:
        races = json.load(h)
    return {str(r.get("date", "")): r for r in races if r.get("date")}


def _unify_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Cast mixed-type columns to string (e.g. '+1 LAP' vs 12.4). Records them."""
    if not rows:
        return rows, []
    kinds: dict[str, set[str]] = {}
    for r in rows:
        for key, val in r.items():
            if val is not None:
                kinds.setdefault(key, set()).add(type(val).__name__)
    mixed = [k for k, t in kinds.items() if len(t) > 1]
    if not mixed:
        return rows, []
    fixed = []
    for r in rows:
        row = dict(r)
        for key in mixed:
            if row.get(key) is not None:
                row[key] = str(row[key])
        fixed.append(row)
    return fixed, mixed


def write_partition(path: str, rows: list[dict]) -> tuple[int, str]:
    """Write one parquet partition; return (n_rows, sha256). Skip if verified."""
    if os.path.exists(path) and rows:
        try:
            existing = pq.read_table(path).num_rows
            if existing == len(rows):
                return existing, sha256_file(path)
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows, _ = _unify_rows(rows)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="snappy")
    return len(rows), sha256_file(path)


_RESOLVE = None  # set in main() before canonicalization
_SEASON_DRIVERS: dict[int, set[str]] = {}
_RESOLUTION_STATS: dict[str, int] = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}


def resolve_driver(driver_ref: str, _registry=None, season: int | None = None) -> str | None:
    """Resolve a Jolpica driverId to canonical driver_id (None when unknown)."""
    assert _RESOLVE is not None, "resolver not initialised"
    found, status = _RESOLVE(str(driver_ref), season)
    _RESOLUTION_STATS[status] = _RESOLUTION_STATS.get(status, 0) + 1
    return found


def canonicalize_jolpica_laps(rmap: dict, registry, manifest: dict) -> None:
    """Convert raw Jolpica lap pages to canonical partitions."""
    fam = os.path.join(CANON, "laps_jolpica")
    total, files, orphans = 0, 0, 0
    for season in sorted(os.listdir(os.path.join(RAW_JOLPICA, "laps"))):
        sdir = os.path.join(RAW_JOLPICA, "laps", season)
        if not os.path.isdir(sdir):
            continue
        for rnd in sorted(os.listdir(sdir), key=lambda x: int(x)):
            rdir = os.path.join(sdir, rnd)
            if not os.path.isdir(rdir):
                continue
            race = rmap.get((int(season), int(rnd)))
            race_id = race["race_id"] if race else f"{season}-r{int(rnd):02d}"
            if race is None:
                orphans += 1
            rows: list[dict] = []
            for page in sorted(glob.glob(os.path.join(rdir, "*.json"))):
                if page.endswith(".provenance.json"):
                    continue
                with open(page, encoding="utf-8") as h:
                    payload = json.load(h)
                normed, _ = normalize_jolpica_laps(
                    payload, source_file=os.path.basename(page),
                    season=int(season), round_no=int(rnd))
                for r in normed:
                    prov = r["provenance"]
                    rows.append({
                        "lap_id": f"{race_id}:{r['driver_ref']}:{r['lap_number']}",
                        "race_id": race_id,
                        "season": int(season),
                        "round": int(rnd),
                        "driver_ref": r["driver_ref"],
                        "driver_id": resolve_driver(r["driver_ref"], registry, season=int(season)),
                        "lap_number": r["lap_number"],
                        "lap_time_seconds": r["lap_time_seconds"],
                        "position": r["position"],
                        "source": "jolpica-laps",
                        "source_version": "api.jolpi.ca",
                        "retrieved_at": prov["ingested_at"],
                        "source_record_id": prov["source_record_id"],
                        "raw_sha256": sha256_file(page),
                        "evidence_tier": "PARTIAL",
                        "canonicalization_version": CANON_VERSION,
                    })
            rows.sort(key=lambda r: (r["lap_number"] or 0, r["driver_ref"]))
            n, sha = write_partition(
                os.path.join(fam, f"season={season}", f"round={rnd}", "part-000.parquet"), rows)
            total += n
            files += 1
    manifest["laps_jolpica"] = {"rows": total, "partitions": files, "orphan_races": orphans}


def canonicalize_jolpica_pits(rmap: dict, registry, manifest: dict) -> None:
    """Convert raw Jolpica pit pages to canonical partitions (totals only)."""
    fam = os.path.join(CANON, "pitstops_jolpica")
    total, files, orphans = 0, 0, 0
    pdir = os.path.join(RAW_JOLPICA, "pitstops")
    if not os.path.isdir(pdir):
        manifest["pitstops_jolpica"] = {"rows": 0, "partitions": 0, "orphan_races": 0}
        return
    for season in sorted(os.listdir(pdir)):
        sdir = os.path.join(pdir, season)
        if not os.path.isdir(sdir):
            continue
        for rnd in sorted(os.listdir(sdir), key=lambda x: int(x)):
            rdir = os.path.join(sdir, rnd)
            if not os.path.isdir(rdir):
                continue
            race = rmap.get((int(season), int(rnd)))
            race_id = race["race_id"] if race else f"{season}-r{int(rnd):02d}"
            if race is None:
                orphans += 1
            rows = []
            for page in sorted(glob.glob(os.path.join(rdir, "*.json"))):
                if page.endswith(".provenance.json"):
                    continue
                with open(page, encoding="utf-8") as h:
                    payload = json.load(h)
                normed, _ = normalize_jolpica_pitstops(
                    payload, source_file=os.path.basename(page),
                    season=int(season), round_no=int(rnd))
                for r in normed:
                    prov = r["provenance"]
                    rows.append({
                        "pitstop_id": f"{race_id}:{r['driver_ref']}:{r['stop_number']}",
                        "race_id": race_id,
                        "season": int(season),
                        "round": int(rnd),
                        "driver_ref": r["driver_ref"],
                        "driver_id": resolve_driver(r["driver_ref"], registry, season=int(season)),
                        "pit_lap": r["pit_lap"],
                        "stop_number": r["stop_number"],
                        "duration_seconds": r["total_pit_loss_seconds"],
                        "stationary_seconds": None,  # NOT split by source
                        "lane_loss_seconds": None,  # NOT split by source
                        "time_of_day": r["time_of_day"],
                        "observed_date": prov["observed_at"],
                        "source": "jolpica-pitstops",
                        "source_version": "api.jolpi.ca",
                        "retrieved_at": prov["ingested_at"],
                        "source_record_id": prov["source_record_id"],
                        "raw_sha256": sha256_file(page),
                        "evidence_tier": "PARTIAL",
                        "canonicalization_version": CANON_VERSION,
                    })
            rows.sort(key=lambda r: ((r["pit_lap"] or 0), r["driver_ref"]))
            n, _ = write_partition(
                os.path.join(fam, f"season={season}", f"round={rnd}", "part-000.parquet"), rows)
            total += n
            files += 1
    manifest["pitstops_jolpica"] = {"rows": total, "partitions": files, "orphan_races": orphans}


def _scalarize(records: list[dict]) -> tuple[list[dict], list[str]]:
    """Keep scalar columns; drop nested lists/dicts (recorded, never guessed)."""
    dropped: set[str] = set()
    out = []
    for rec in records:
        row = {}
        for key, val in rec.items():
            if isinstance(val, (list, dict)):
                dropped.add(key)
            else:
                row[key] = val
        out.append(row)
    return out, sorted(dropped)


def canonicalize_openf1(manifest: dict, skip: set | None = None) -> None:
    """Convert raw OpenF1 endpoint files to canonical partitions."""
    skip = skip or set()
    normals = {"laps": normalize_openf1_laps, "stints": normalize_openf1_stints,
               "weather": normalize_openf1_weather, "pit": normalize_openf1_pit,
               "race_control": normalize_openf1_race_control}
    by_date = date_to_race()
    # session_key -> (season, race_id) via cached sessions files
    smap: dict[int, dict] = {}
    for path in glob.glob(os.path.join(RAW_OPENF1, "sessions", "*.json")):
        if path.endswith(".provenance.json"):
            continue
        year = os.path.basename(path).split(".json")[0]
        with open(path, encoding="utf-8") as h:
            for s in json.load(h):
                race = by_date.get(str(s.get("date_start", ""))[:10])
                smap[int(s["session_key"])] = {
                    "season": int(year),
                    "race_id": race["race_id"] if race else "",
                    "session_name": s.get("session_name", ""),
                }
    families = {"laps": "laps_openf1", "stints": "stints_openf1",
                "weather": "weather_openf1", "pit": "pitstops_openf1",
                "race_control": "race_control_openf1", "position": "positions_openf1",
                "overtakes": "overtakes_openf1", "team_radio": "teamradio_openf1",
                "session_result": "results_openf1", "drivers": "drivers_openf1",
                "intervals": "intervals_openf1"}
    for endpoint, family in families.items():
        if endpoint in skip or family in skip:
            print(f"[{utc_now_iso()}] family {family}: SKIPPED (raw preserved)", flush=True)
            continue
        fam = os.path.join(CANON, family)
        total, files, orphans = 0, 0, 0
        print(f"[{utc_now_iso()}] family {family} ...", flush=True)
        for path in sorted(glob.glob(os.path.join(RAW_OPENF1, endpoint, "*.json"))):
            if path.endswith(".provenance.json"):
                continue
            session_key = int(os.path.basename(path).split(".json")[0])
            meta = smap.get(session_key, {})
            season = meta.get("season", 0)
            race_id = meta.get("race_id", "")
            if not race_id:
                orphans += 1
            with open(path, encoding="utf-8") as h:
                records = json.load(h)
            if not isinstance(records, list):
                records = []
            norm = normals.get(endpoint)
            if norm is not None:
                rows, _ = norm(records, source_file=os.path.basename(path))
                for r in rows:
                    prov = r.pop("provenance")
                    r.update({
                        "race_id": race_id, "season": season,
                        "session_key": session_key,
                        "source": f"openf1-{endpoint}",
                        "retrieved_at": prov["ingested_at"],
                        "source_record_id": prov["source_record_id"],
                        "raw_sha256": sha256_file(path),
                        "evidence_tier": "PARTIAL",
                        "canonicalization_version": CANON_VERSION,
                    })
            else:
                rows, dropped = _scalarize(records)
                manifest.setdefault("dropped_nested_columns", {})[family] = dropped
                for r in rows:
                    r.update({
                        "race_id": race_id, "season": season,
                        "session_key": session_key,
                        "source": f"openf1-{endpoint}",
                        "raw_sha256": sha256_file(path),
                        "evidence_tier": "LIMITED",
                        "canonicalization_version": CANON_VERSION,
                    })
            n, _ = write_partition(
                os.path.join(fam, f"season={season}", f"session={session_key}",
                             "part-000.parquet"), rows)
            total += n
            files += 1
        manifest[family] = {"rows": total, "partitions": files,
                            "orphan_sessions": orphans}
        print(f"[{utc_now_iso()}] family {family}: {total} rows, {files} partitions", flush=True)


def canonicalize_era5(manifest: dict) -> None:
    """Convert raw ERA5 files to canonical partitions (REANALYSIS-labeled)."""
    from app.data.external.normalization import normalize_openmeteo_hourly  # noqa: E402
    fam = os.path.join(CANON, "reanalysis_era5")
    total, files = 0, 0
    for path in sorted(glob.glob(os.path.join(RAW_ERA5, "*.json"))):
        if path.endswith(".provenance.json"):
            continue
        race_id = os.path.basename(path).split(".json")[0]
        with open(path, encoding="utf-8") as h:
            payload = json.load(h)
        rows, _ = normalize_openmeteo_hourly(payload, source_file=os.path.basename(path),
                                             latitude=0.0, longitude=0.0, race_id=race_id)
        for r in rows:
            prov = r.pop("provenance")
            r.update({
                "source": "openmeteo-era5",
                "retrieved_at": prov["ingested_at"],
                "source_record_id": prov["source_record_id"],
                "raw_sha256": sha256_file(path),
                "evidence_tier": "LIMITED",
                "canonicalization_version": CANON_VERSION,
            })
        n, _ = write_partition(os.path.join(fam, f"race={race_id}", "part-000.parquet"), rows)
        total += n
        files += 1
    manifest["reanalysis_era5"] = {"rows": total, "partitions": files}


def main() -> int:
    """Entry point."""
    ap = argparse.ArgumentParser(description="Phase 22.6 canonicalization")
    ap.add_argument("--families", default="",
                    help="comma list to limit (default: all)")
    ap.add_argument("--exclude", default="intervals",
                    help="comma list to skip (default: intervals — raw preserved, deferred)")
    args = ap.parse_args()
    only = {f.strip() for f in args.families.split(",") if f.strip()}
    skip = {f.strip() for f in args.exclude.split(",") if f.strip()}

    with open(os.path.join(CANON, "drivers.json"), encoding="utf-8") as h:
        drivers = json.load(h)
    registry, by_last = build_driver_lookup(drivers)
    with open(os.path.join(CANON, "results.json"), encoding="utf-8") as h:
        season_drivers = season_driver_ids(json.load(h))
    global _RESOLVE
    _RESOLVE = lambda ref, season=None: resolve_driver_ref(  # noqa: E731
        ref, registry, by_last, season, season_drivers)
    rmap = race_map()
    previous: dict = {}
    if os.path.exists(CANON_MANIFEST):
        try:
            with open(CANON_MANIFEST, encoding="utf-8") as h:
                previous = json.load(h).get("families", {})
        except (json.JSONDecodeError, OSError):
            previous = {}
    manifest: dict = {"canonicalization_version": CANON_VERSION,
                      "generated_at": utc_now_iso(), "families": dict(previous)}
    fam = manifest["families"]

    def wanted(name: str) -> bool:
        if name == "openf1":
            return (not only or "openf1" in only)
        return (not only or name in only) and name not in skip

    if wanted("laps_jolpica"):
        canonicalize_jolpica_laps(rmap, registry, fam)
    if wanted("pitstops_jolpica"):
        canonicalize_jolpica_pits(rmap, registry, fam)
    if wanted("openf1"):
        canonicalize_openf1(fam, skip=skip)
    if wanted("era5"):
        canonicalize_era5(fam)

    with open(CANON_MANIFEST, "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, sort_keys=True)
    manifest["driver_resolution"] = dict(_RESOLUTION_STATS)
    with open(CANON_MANIFEST, "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, sort_keys=True)
    print(json.dumps(fam, indent=1))
    print(json.dumps({"driver_resolution": _RESOLUTION_STATS}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
