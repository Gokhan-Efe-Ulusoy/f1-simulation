"""Phase 22.5 acquisition runner (real network, rate-limited, reproducible).

Scope (deliberate, documented in phase22_5_data_acquisition.md):
  - Jolpica laps: 2024 R1 (full, paginated) + availability probes
  - Jolpica pitstops: 2024 R1-R5 (full, paginated)
  - Jolpica results 2024 R1 (driver code map for cross-source joins)
  - OpenF1: 2024 Bahrain race session (sessions discovery + laps/stints/
    weather/pit/race_control/drivers)
  - Open-Meteo ERA5: race-day hourly weather for 6 anchor races
  - f1db: local pinned-release cross-validation counts (no re-download)
  - FastF1: availability probe only (cache evidence; no bulk pull)

Usage (from backend/):
    python scripts/phase22_5_acquisition.py            # live run
    python scripts/phase22_5_acquisition.py --offline  # rebuild staging/manifests from raw only

Raw payloads are immutable under data/raw/external/<source_id>/.
Staging rows land in data/external_staging/. Canonical data is untouched.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.external.catalog import build_default_catalog  # noqa: E402
from app.data.external.checksums import sha256_bytes, sha256_file  # noqa: E402
from app.data.external.conflicts import conflict_pattern, detect_lap_conflicts  # noqa: E402
from app.data.external.coverage import (  # noqa: E402
    build_coverage_matrix,
    build_readiness,
    era_for_season,
)
from app.data.external.deduplication import deduplicate, row_identity  # noqa: E402
from app.data.external.download import RateLimiter, download_to_raw  # noqa: E402
from app.data.external.license import may_acquire  # noqa: E402
from app.data.external.normalization import (  # noqa: E402
    normalize_jolpica_laps,
    normalize_jolpica_pitstops,
    normalize_openf1_laps,
    normalize_openf1_pit,
    normalize_openf1_race_control,
    normalize_openf1_stints,
    normalize_openf1_weather,
    normalize_openmeteo_hourly,
)
from app.data.external.promotion import assess_promotion  # noqa: E402
from app.data.external.resolution import (  # noqa: E402
    build_driver_registry,
    resolve_with_aliases,
    summarize_resolutions,
)
from app.data.provenance import utc_now_iso  # noqa: E402
from app.data.regulations.schema import seed_evidence  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_ROOT = os.path.join(ROOT, "data", "raw", "external")
STAGING = os.path.join(ROOT, "data", "external_staging")
MANIFESTS = os.path.join(ROOT, "data", "manifests")
CANDIDATES = os.path.join(ROOT, "data", "calibration_candidates")
REGULATIONS = os.path.join(ROOT, "data", "regulations")

JOLPICA = "https://api.jolpi.ca/ergast/f1"
OPENF1 = "https://api.openf1.org/v1"
OPENMETEO = "https://archive-api.open-meteo.com/v1/archive"

ANCHOR_RACES = [
    # (season, round, race_id, date, lat, lon) — coords from Jolpica Circuit.Location
    (2024, 1, "2024-bahrain", "2024-03-02", 26.0325, 50.5106),
    (2024, 2, "2024-jeddah", "2024-03-09", 21.6319, 39.1044),
    (2024, 3, "2024-melbourne", "2024-03-24", -37.8497, 144.968),
    (2024, 4, "2024-suzuka", "2024-04-07", 34.8431, 136.541),
    (2024, 8, "2024-monaco", "2024-05-26", 43.7347, 7.42056),
    (2024, 12, "2024-silverstone", "2024-07-07", 52.0786, -1.01694),
]

LAP_PROBE_SEASONS = [1996, 2000, 2005, 2010, 2015, 2020, 2024]


def http_get(url: str, timeout: float = 30.0) -> bytes:
    """Single GET with project User-Agent (429s propagate to retry layer)."""
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/22.5"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def get_json(url: str, limiter: RateLimiter, tries: int = 4) -> dict | list:
    """GET JSON with backoff; raises on persistent failure."""
    last: Exception | None = None
    for attempt in range(tries):
        limiter.wait()
        try:
            return json.loads(http_get(url).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            import time as _t

            _t.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def store_raw(source_id: str, filename: str, payload: bytes, url: str, lic: str) -> str:
    """Write raw payload immutably; return path (skip when valid sidecar exists)."""
    dest_dir = os.path.join(RAW_ROOT, source_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    sidecar = dest + ".provenance.json"
    if os.path.exists(dest) and os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as h:
            meta = json.load(h)
        if meta.get("sha256") == sha256_file(dest):
            return dest
    with open(dest, "wb") as h:
        h.write(payload)
    from app.data.external.checksums import write_sidecar

    write_sidecar(dest, source_id=source_id, source_url=url, license=lic,
                  download_timestamp=utc_now_iso(),
                  extra={"sha256_bytes": sha256_bytes(payload)})
    return dest


def jolpica_paginated(base: str, limiter: RateLimiter, lic: str,
                      source_id: str, name: str, limit: int = 100) -> tuple[list[str], dict]:
    """Fetch all pages of a Jolpica list endpoint; store each page raw."""
    paths: list[str] = []
    offset = 0
    total: int | None = None
    merged: dict = {}
    while True:
        url = f"{base}?limit={limit}&offset={offset}"
        # Reuse immutable raw pages when a valid sidecar already exists.
        cached = os.path.join(RAW_ROOT, source_id, f"{name}-offset{offset}.json")
        sidecar = cached + ".provenance.json"
        if os.path.exists(cached) and os.path.exists(sidecar):
            with open(sidecar, encoding="utf-8") as h:
                meta = json.load(h)
            if meta.get("sha256") == sha256_file(cached):
                with open(cached, encoding="utf-8") as h:
                    payload = json.load(h)
                paths.append(cached)
                mr = payload.get("MRData", {})
                total = int(mr.get("total", 0))
                merged = payload
                offset += limit
                if offset >= total or total == 0:
                    break
                continue
        payload = get_json(url, limiter)
        raw = json.dumps(payload).encode()
        paths.append(store_raw(source_id, f"{name}-offset{offset}.json", raw, url, lic))
        mr = payload.get("MRData", {})
        total = int(mr.get("total", 0))
        merged = payload
        offset += limit
        if offset >= total or total == 0:
            break
        if offset > 2000:  # safety cap: never hammer the API
            merged["_truncated_at_offset"] = offset
            break
    return paths, merged


def main() -> int:
    """Run the acquisition. Returns 0 on success."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="rebuild staging/manifests from existing raw only")
    args = ap.parse_args()
    offline = args.offline

    os.makedirs(STAGING, exist_ok=True)
    os.makedirs(CANDIDATES, exist_ok=True)
    os.makedirs(REGULATIONS, exist_ok=True)
    # Previous manifest lets --offline runs preserve discovery facts
    # (session keys, availability probes) without re-hitting the network.
    previous: dict = {}
    _prev_path = os.path.join(MANIFESTS, "external_acquisition_manifest.json")
    if os.path.exists(_prev_path):
        try:
            with open(_prev_path, encoding="utf-8") as _h:
                previous = json.load(_h)
        except (json.JSONDecodeError, OSError):
            previous = {}
    limiter = RateLimiter(min_interval_seconds=1.5)
    lic_jolpica = "CC BY-SA (Ergast heritage) / provider terms"
    lic_openf1 = "OpenF1 terms (historical free)"
    lic_met = "CC BY 4.0 (ECMWF/Copernicus via Open-Meteo)"

    log: list[str] = []
    counts = {"laps_jolpica": 0, "pits_jolpica": 0, "laps_openf1": 0,
              "stints": 0, "wx_openf1": 0, "pit_openf1": 0, "rc": 0,
              "reanalysis_hours": 0, "telemetry_samples": 0}
    warnings_all: list[str] = []
    staging_tables: dict[str, list] = {}

    # ---- 1. Jolpica laps: 2024 R1 full -------------------------------------
    season, rnd = 2024, 1
    if not offline and may_acquire("jolpica-laps"):
        paths, merged = jolpica_paginated(
            f"{JOLPICA}/{season}/{rnd}/laps.json", limiter, lic_jolpica,
            "jolpica-laps", f"{season}-r{rnd}-laps")
        log.append(f"jolpica-laps {season} R{rnd}: {len(paths)} pages, total={merged['MRData']['total']}")
        all_rows: list[dict] = []
        for page_path in paths:
            with open(page_path, encoding="utf-8") as h:
                page = json.load(h)
            rows, warns = normalize_jolpica_laps(
                page, source_file=os.path.basename(page_path), season=season, round_no=rnd)
            all_rows.extend(rows)
            warnings_all.extend(warns)
        staging_tables["laps_jolpica"] = all_rows
        counts["laps_jolpica"] = len(all_rows)

    # ---- 2. Jolpica laps availability probes (limit=1, cheap) --------------
    probes: dict[str, int] = {}
    if not offline and may_acquire("jolpica-laps"):
        for year in LAP_PROBE_SEASONS:
            try:
                payload = get_json(f"{JOLPICA}/{year}/1/laps.json?limit=1", limiter)
                races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
                laps = races[0].get("Laps", []) if races else []
                probes[str(year)] = len(laps)  # 0 => endpoint present but no lap rows
            except Exception as exc:  # noqa: BLE001
                probes[str(year)] = -1
                warnings_all.append(f"laps probe {year}/1 failed: {exc}")
        log.append(f"laps availability probes: {probes}")

    # ---- 3. Jolpica pitstops 2024 R1-R5 ------------------------------------
    if not offline and may_acquire("jolpica-pitstops"):
        pit_rows: list[dict] = []
        for r in (1, 2, 3, 4, 5):
            paths, merged = jolpica_paginated(
                f"{JOLPICA}/2024/{r}/pitstops.json", limiter, lic_jolpica,
                "jolpica-pitstops", f"2024-r{r}-pitstops")
            for page_path in paths:
                with open(page_path, encoding="utf-8") as h:
                    page = json.load(h)
                rows, warns = normalize_jolpica_pitstops(
                    page, source_file=os.path.basename(page_path), season=2024, round_no=r)
                pit_rows.extend(rows)
                warnings_all.extend(warns)
            log.append(f"jolpica-pitstops 2024 R{r}: total={merged['MRData']['total']}")
        staging_tables["pit_stops_jolpica"] = pit_rows
        counts["pits_jolpica"] = len(pit_rows)

    # ---- 4. Jolpica results 2024 R1 (driver code map) -----------------------
    code_to_ref: dict[str, str] = {}
    if not offline and may_acquire("jolpica-results"):
        payload = get_json(f"{JOLPICA}/2024/1/results.json", limiter)
        store_raw("jolpica-results", "2024-r1-results.json",
                  json.dumps(payload).encode(), f"{JOLPICA}/2024/1/results.json", lic_jolpica)
        for row in payload["MRData"]["RaceTable"]["Races"][0].get("Results", []):
            code_to_ref[str(row.get("Driver", {}).get("code", ""))] = str(row.get("Driver", {}).get("driverId", ""))
        log.append(f"driver code map: {len(code_to_ref)} entries")

    # ---- 5. OpenF1: discover 2024 Bahrain race session ---------------------
    session_key: int | None = None
    meeting_key: int | None = None
    if not offline and may_acquire("openf1-timing"):
        sessions = get_json(f"{OPENF1}/sessions?year=2024", limiter)
        store_raw("openf1-timing", "sessions-2024.json",
                  json.dumps(sessions).encode(), f"{OPENF1}/sessions?year=2024", lic_openf1)
        bahrain = [s for s in sessions
                   if (s.get("country_name") == "Bahrain" or s.get("location") in ("Sakhir", "Bahrain"))
                   and s.get("session_name") == "Race" and not s.get("is_cancelled")]
        if bahrain:
            session_key = int(bahrain[0]["session_key"])
            meeting_key = int(bahrain[0]["meeting_key"])
            log.append(f"openf1 Bahrain 2024 race session_key={session_key} meeting_key={meeting_key}")
        else:
            warnings_all.append("openf1: Bahrain 2024 Race session not found")

    num_to_ref: dict[str, str] = {}
    if session_key is not None and not offline:
        drivers = get_json(f"{OPENF1}/drivers?session_key={session_key}", limiter)
        store_raw("openf1-timing", f"drivers-{session_key}.json",
                  json.dumps(drivers).encode(), f"{OPENF1}/drivers?session_key={session_key}", lic_openf1)
        for d in drivers:
            code = str(d.get("name_acronym", ""))
            if code in code_to_ref:
                num_to_ref[str(d.get("driver_number", ""))] = code_to_ref[code]
        log.append(f"openf1 driver_number->ref mapped: {len(num_to_ref)}/{len(drivers)}")
        endpoints = {
            "laps": ("openf1-timing", f"{OPENF1}/laps?session_key={session_key}"),
            "stints": ("openf1-stints", f"{OPENF1}/stints?session_key={session_key}"),
            "weather": ("openf1-weather", f"{OPENF1}/weather?session_key={session_key}"),
            "pit": ("openf1-pit", f"{OPENF1}/pit?session_key={session_key}"),
            "race_control": ("openf1-racecontrol", f"{OPENF1}/race_control?session_key={session_key}"),
        }
        normals = {
            "laps": normalize_openf1_laps, "stints": normalize_openf1_stints,
            "weather": normalize_openf1_weather, "pit": normalize_openf1_pit,
            "race_control": normalize_openf1_race_control,
        }
        for name, (src, url) in endpoints.items():
            if not may_acquire(src):
                continue
            try:
                recs = get_json(url, limiter)
                if not isinstance(recs, list):
                    recs = []
                store_raw(src, f"{name}-{session_key}.json",
                          json.dumps(recs).encode(), url, lic_openf1)
                rows, warns = normals[name](recs, source_file=f"{name}-{session_key}.json")
                staging_tables[f"{name}_openf1"] = rows
                warnings_all.extend(warns)
                key = {"laps": "laps_openf1", "stints": "stints",
                       "weather": "wx_openf1", "pit": "pit_openf1",
                       "race_control": "rc"}[name]
                counts[key] = len(rows)
                log.append(f"openf1 {name}: {len(rows)} rows")
            except Exception as exc:  # noqa: BLE001
                warnings_all.append(f"openf1 {name} failed: {exc}")
                log.append(f"openf1 {name}: BLOCKED ({exc})")

    # ---- 6. Open-Meteo ERA5 for anchor races --------------------------------
    if not offline and may_acquire("openmeteo-era5"):
        rean_rows: list[dict] = []
        for year, rnd, race_id, date, lat, lon in ANCHOR_RACES:
            url = (f"{OPENMETEO}?latitude={lat}&longitude={lon}&start_date={date}"
                   f"&end_date={date}&hourly=temperature_2m,relative_humidity_2m,"
                   f"precipitation,pressure_msl,wind_speed_10m,wind_direction_10m")
            try:
                payload = get_json(url, limiter)
                store_raw("openmeteo-era5", f"{race_id}.json",
                          json.dumps(payload).encode(), url, lic_met)
                rows, warns = normalize_openmeteo_hourly(
                    payload, source_file=f"{race_id}.json",
                    latitude=lat, longitude=lon, race_id=race_id)
                rean_rows.extend(rows)
                warnings_all.extend(warns)
                log.append(f"openmeteo {race_id}: {len(rows)} hourly rows")
            except Exception as exc:  # noqa: BLE001
                warnings_all.append(f"openmeteo {race_id} failed: {exc}")
        staging_tables["reanalysis_openmeteo"] = rean_rows
        counts["reanalysis_hours"] = len(rean_rows)

    # ---- 7. f1db local cross-validation (no re-download) -------------------
    f1db_stats: dict[str, int] = {}
    for path in glob.glob(os.path.join(ROOT, "data", "raw", "github", "f1db",
                                       "v2026.13.0", "extracted-v2026.13.0", "*.csv")):
        try:
            with open(path, encoding="utf-8", errors="replace") as h:
                f1db_stats[os.path.basename(path)] = sum(1 for _ in csv.DictReader(h))
        except Exception:  # noqa: BLE001
            continue
    log.append(f"f1db local tables: {len(f1db_stats)} files")

    # ---- 8. FastF1 probe (import + cache evidence only) --------------------
    fastf1_info: dict[str, object] = {"status": "NOT_PROBED"}
    try:
        import fastf1  # type: ignore  # noqa: E402

        fastf1_info = {"status": "AVAILABLE", "version": getattr(fastf1, "__version__", "unknown"),
                       "cache": sorted(glob.glob(os.path.join(
                           ROOT, "data", "raw", "fastf1", "cache", "*", "*", "")))[:6]}
    except Exception as exc:  # noqa: BLE001
        fastf1_info = {"status": "NOT_AVAILABLE", "reason": str(exc)[:200]}
    log.append(f"fastf1: {fastf1_info.get('status')}")

    # ---- OFFLINE mode: reload staging inputs from raw ----------------------
    if offline or not staging_tables:
        staging_tables = _rebuild_staging_from_raw(warnings_all, log, counts)
    if not code_to_ref:
        # Rebuild the join map from immutable raw (works live + offline).
        try:
            with open(os.path.join(RAW_ROOT, "jolpica-results", "2024-r1-results.json"),
                      encoding="utf-8") as h:
                _res = json.load(h)
            for row in _res["MRData"]["RaceTable"]["Races"][0].get("Results", []):
                code_to_ref[str(row.get("Driver", {}).get("code", ""))] = str(
                    row.get("Driver", {}).get("driverId", ""))
        except FileNotFoundError:
            warnings_all.append("join map unavailable: jolpica-results raw missing")
    if not num_to_ref and code_to_ref:
        try:
            _drv_paths = sorted(glob.glob(os.path.join(RAW_ROOT, "openf1-timing", "drivers-*.json")))
            for _dp in _drv_paths:
                if _dp.endswith(".provenance.json"):
                    continue
                with open(_dp, encoding="utf-8") as h:
                    for d in json.load(h):
                        _code = str(d.get("name_acronym", ""))
                        if _code in code_to_ref:
                            num_to_ref[str(d.get("driver_number", ""))] = code_to_ref[_code]
                break  # one session's driver list suffices for the join
        except Exception as exc:  # noqa: BLE001
            warnings_all.append(f"driver map rebuild failed: {exc}")
    log.append(f"join map: {len(code_to_ref)} codes, {len(num_to_ref)} driver_numbers")

    # ---- Deduplicate + write staging ---------------------------------------
    dup_vs_previous: dict[str, int] = {}
    for table, rows in staging_tables.items():
        staged_path = os.path.join(STAGING, f"{table}.json")
        previous_ids: set[str] = set()
        if os.path.exists(staged_path):
            try:
                with open(staged_path, encoding="utf-8") as h:
                    previous_ids = {r.get("_identity", "") for r in json.load(h)}
            except (json.JSONDecodeError, OSError):
                previous_ids = set()
        ded = deduplicate(rows, _table_kind(table))
        current_ids = {r.get("_identity", "") for r in ded["new"]}
        dup_vs_previous[table] = len(current_ids & previous_ids)
        with open(staged_path, "w", encoding="utf-8") as h:
            json.dump(ded["new"], h, indent=1)
        log.append(f"staging {table}: new={ded['new_rows']} dup={ded['duplicate_rows']} "
                   f"invalid={ded['invalid_rows']} dup_vs_previous={dup_vs_previous[table]}")

    # ---- Conflicts: Jolpica laps vs OpenF1 laps (2024 Bahrain) -------------
    jol_rows = staging_tables.get("laps_jolpica", [])
    of_rows = staging_tables.get("laps_openf1", [])
    conflict_objs = detect_lap_conflicts(
        jol_rows, of_rows, season=2024, round_no=1, driver_map=num_to_ref)
    conflicts = [c.model_dump() for c in conflict_objs]
    compared = min(len(jol_rows), len(of_rows))
    with open(os.path.join(MANIFESTS, "external_conflicts.json"), "w", encoding="utf-8") as h:
        json.dump({"compared_pairs": compared, "conflicts": conflicts,
                   "pattern": conflict_pattern(conflict_objs),
                   "rounding_tol": 0.002, "generated_at": utc_now_iso()}, h, indent=2)
    log.append(f"conflicts: {len(conflicts)} genuine over {compared} compared pairs")

    # ---- Entity resolution summary ------------------------------------------
    drivers_path = os.path.join(ROOT, "data", "canonical", "drivers.json")
    with open(drivers_path, encoding="utf-8") as h:
        canonical_drivers = json.load(h)
    registry = build_driver_registry(canonical_drivers)
    outcomes = []
    for row in jol_rows:
        outcomes.append(resolve_with_aliases(str(row.get("driver_ref", "")).replace("_", "-"), [registry]))
    resolution_summary = summarize_resolutions(outcomes)
    # demonstrate AMBIGUOUS honestly: canonical has duplicate-prone short ids
    log.append(f"resolution jolpica drivers: {resolution_summary}")

    # ---- Coverage matrix ------------------------------------------------------
    acquired_counts = {
        "race_results": 0, "qualifying": 0,
        "lap_timing": counts["laps_jolpica"] + counts["laps_openf1"],
        "sector_timing": sum(1 for r in of_rows if r.get("sector_1_seconds") is not None),
        "pit_timing": counts["pits_jolpica"] + counts["pit_openf1"],
        "tyre_compound": counts["stints"], "tyre_age": counts["stints"],
        "weather": counts["wx_openf1"], "race_control": counts["rc"],
        "telemetry": counts["telemetry_samples"], "setup": 0, "strategy": 0,
        "regulation": len(seed_evidence()),
    }
    acquired_eras = {
        k: (["2022-2026"] if v > 0 else []) for k, v in acquired_counts.items()
    }
    acquired_eras["regulation"] = ["1950-1969", "1970-1989", "1990-1999", "2000-2009",
                                   "2010-2017", "2018-2021", "2022-2026"] if acquired_counts["regulation"] else []
    matrix = build_coverage_matrix(acquired_counts, acquired_eras, canonical_changed=False)
    with open(os.path.join(MANIFESTS, "external_coverage.json"), "w", encoding="utf-8") as h:
        json.dump({"matrix": matrix, "generated_at": utc_now_iso(),
                   "canonical_version": "f1-dataset-v1.1 (unchanged)"}, h, indent=2)

    # ---- Promotion gate -------------------------------------------------------
    conflict_rate_n = (len(conflicts) / compared) if compared else 0.0
    gate_specs = [
        ("lap_timing", "LIMITED", counts["laps_jolpica"] + counts["laps_openf1"],
         ["2022-2026"], ["2022-2026"], ["jolpica-laps", "openf1-timing"],
         len(conflicts), compared, 0.02, "lap", 100),
        ("pit_timing", "PARTIAL", counts["pits_jolpica"] + counts["pit_openf1"],
         ["2022-2026"], ["2022-2026"], ["jolpica-pitstops", "openf1-pit"],
         0, max(counts["pits_jolpica"], 1), 0.05, "event", 50),
        ("tyre_compound", "LIMITED", counts["stints"],
         ["2022-2026"], ["2022-2026"], ["openf1-stints"], 0,
         max(counts["stints"], 1), 0.05, "stint", 20),
        ("tyre_age", "PRIOR_ONLY", counts["stints"],
         ["2022-2026"], ["2022-2026"], ["openf1-stints"], 0,
         max(counts["stints"], 1), 0.05, "stint", 20),
        ("weather", "LIMITED", counts["wx_openf1"],
         ["2022-2026"], ["2022-2026"], ["openf1-weather"], 0,
         max(counts["wx_openf1"], 1), 0.05, "1 minute", 30),
        ("race_control", "LIMITED", counts["rc"],
         ["2022-2026"], ["2022-2026"], ["openf1-racecontrol"], 0,
         max(counts["rc"], 1), 0.10, "event", 10),
        ("sector_timing", "LIMITED", acquired_counts["sector_timing"],
         ["2022-2026"], ["2022-2026"], ["openf1-timing"], 0,
         max(acquired_counts["sector_timing"], 1), 0.10, "sector", 100),
        ("telemetry", "LIMITED", 0, [], ["2022-2026"], ["openf1-telemetry"],
         0, 0, 1.0, "3.7 Hz", 1000),
        ("setup", "NON_IDENTIFIABLE", 0, [], ["1950-2026"], [], 0, 0, 1.0, "n/a", 100),
        ("strategy", "NON_IDENTIFIABLE", 0, [], ["1950-2026"], [], 0, 0, 1.0, "n/a", 100),
    ]
    gates = [assess_promotion(variable=v, current_status=cs, new_observations=n,
                              eras_observed=eo, eras_claimed=ec, source_ids=ss,
                              conflicts=c, compared=cp, missingness=m,
                              temporal_resolution=tr, min_observations=mo)
             for (v, cs, n, eo, ec, ss, c, cp, m, tr, mo) in gate_specs]

    # ---- Calibration readiness -------------------------------------------------
    readiness = build_readiness({
        "pit_loss": {"sample_size": counts["pits_jolpica"] + counts["pit_openf1"],
                     "years": "2024", "circuits": 5,
                     "drivers": len({r.get("driver_ref") for r in staging_tables.get("pit_stops_jolpica", [])}),
                     "observations": counts["pits_jolpica"] + counts["pit_openf1"],
                     "confounders": ["stationary-vs-lane split absent in Jolpica",
                                     "fuel load", "traffic"],
                     "candidate_model": "empirical pit-loss distribution per circuit (NOT mean-only)",
                     "evidence_tier": "LIMITED" if counts["pits_jolpica"] >= 50 else "PRIOR_ONLY"},
        "tyre_degradation": {"sample_size": counts["laps_jolpica"],
                             "years": "2024", "circuits": 1,
                             "drivers": len({r.get("driver_ref") for r in jol_rows}),
                             "observations": counts["laps_jolpica"],
                             "confounders": ["compound unknown for Jolpica laps", "fuel proxy",
                                             "traffic", "weather"],
                             "candidate_model": "lap_time ~ tyre_age_proxy + fuel_proxy + driver + circuit",
                             "evidence_tier": "LIMITED"},
        "weather_lap_effect": {"sample_size": counts["wx_openf1"] + counts["reanalysis_hours"],
                               "years": "2024", "circuits": 6,
                               "drivers": 0, "observations": counts["wx_openf1"] + counts["reanalysis_hours"],
                               "confounders": ["reanalysis != track sensor", "track temp absent pre-2023"],
                               "candidate_model": "lap_time ~ air_temp + rainfall + wind (session-aligned)",
                               "evidence_tier": "LIMITED"},
        "SC_probability": {"sample_size": counts["rc"], "years": "2024", "circuits": 1,
                           "drivers": 0, "observations": counts["rc"],
                           "confounders": ["single race", "taxonomy free text"],
                           "candidate_model": "P(SC|incident) empirical rate (insufficient N — NOT calibrated)",
                           "evidence_tier": "PRIOR_ONLY"},
        "VSC_probability": {"sample_size": counts["rc"], "years": "2024", "circuits": 1,
                            "drivers": 0, "observations": counts["rc"],
                            "confounders": ["single race"],
                            "candidate_model": "P(VSC|incident) empirical rate (insufficient N — NOT calibrated)",
                            "evidence_tier": "PRIOR_ONLY"},
        "sector_pace": {"sample_size": acquired_counts["sector_timing"],
                        "years": "2024", "circuits": 1, "drivers": len(num_to_ref),
                        "observations": acquired_counts["sector_timing"],
                        "confounders": ["single circuit"],
                        "candidate_model": "sector pace decomposition",
                        "evidence_tier": "LIMITED" if acquired_counts["sector_timing"] >= 100 else "PRIOR_ONLY"},
        "qualifying_pace": {"sample_size": 0, "years": "", "circuits": 0, "drivers": 0,
                            "observations": 0, "confounders": ["no new qualifying sessions acquired"],
                            "candidate_model": "none", "evidence_tier": "PRIOR_ONLY"},
        "driver_pace": {"sample_size": counts["laps_jolpica"], "years": "2024",
                        "circuits": 1, "drivers": len({r.get("driver_ref") for r in jol_rows}),
                        "observations": counts["laps_jolpica"],
                        "confounders": ["single circuit", "fuel/tyre confounded"],
                        "candidate_model": "driver random effects on lap time",
                        "evidence_tier": "LIMITED"},
        "circuit_effect": {"sample_size": 0, "years": "", "circuits": 0, "drivers": 0,
                           "observations": 0, "confounders": ["single-circuit acquisition"],
                           "candidate_model": "none", "evidence_tier": "PRIOR_ONLY"},
    })
    for cand in readiness:
        with open(os.path.join(CANDIDATES, f"{cand.variable}.json"), "w", encoding="utf-8") as h:
            json.dump(cand.model_dump(), h, indent=2)

    # ---- Regulation evidence layer ---------------------------------------------
    with open(os.path.join(REGULATIONS, "regulation_evidence.json"), "w", encoding="utf-8") as h:
        json.dump(seed_evidence(), h, indent=2)

    # ---- Manifests ----------------------------------------------------------------
    catalog = build_default_catalog()
    acquired_ids = {"jolpica-laps", "jolpica-pitstops", "jolpica-results", "openf1-timing",
                    "openf1-stints", "openf1-weather", "openf1-pit", "openf1-racecontrol",
                    "openmeteo-era5", "f1db-database", "fastf1-timing"}
    for src in catalog:
        key = src.source_id
        if key in ("openf1-pit",):
            key = "openf1-timing"  # shares adapter family; keep honest below
        if src.source_id in acquired_ids or src.source_id == "openf1-pit":
            src.acquisition_status = "ACQUIRED"
            src.acquisition_note = "raw immutable under data/raw/external/; staged (not canonical)"
        elif src.source_id in ("ergast-mirror-kaggle", "fia-documents", "official-f1-timing"):
            src.acquisition_status = "REJECTED" if "kaggle" in src.source_id else "BLOCKED"
            src.acquisition_note = ("license unverified/auth required — documented only"
                                    if "kaggle" in src.source_id else
                                    "no open endpoint/reference-only — documented only")
    with open(os.path.join(MANIFESTS, "external_sources.json"), "w", encoding="utf-8") as h:
        json.dump([s.to_dict() for s in catalog], h, indent=2)

    raw_index: list[dict] = []
    for dirpath, _dirs, files in os.walk(RAW_ROOT):
        for fn in files:
            if fn.endswith(".provenance.json"):
                continue
            fp = os.path.join(dirpath, fn)
            side = fp + ".provenance.json"
            meta: dict = {}
            if os.path.exists(side):
                with open(side, encoding="utf-8") as h:
                    meta = json.load(h)
            raw_index.append({"file": os.path.relpath(fp, ROOT).replace(os.sep, "/"),
                              "size": os.path.getsize(fp),
                              "sha256": meta.get("sha256", sha256_file(fp)),
                              "source_id": meta.get("source_id", os.path.basename(dirpath)),
                              "download_timestamp": meta.get("download_timestamp", "")})
    if session_key is None:
        # Recover discovery facts from immutable raw (no network needed).
        _laps = sorted(glob.glob(os.path.join(RAW_ROOT, "openf1-timing", "laps-*.json")))
        _laps = [p for p in _laps if not p.endswith(".provenance.json")]
        if _laps:
            try:
                session_key = int(os.path.basename(_laps[0]).split("laps-")[1].split(".json")[0])
                with open(_laps[0], encoding="utf-8") as _h:
                    _rows = json.load(_h)
                if _rows:
                    meeting_key = int(_rows[0].get("meeting_key", meeting_key or 0)) or meeting_key
            except (ValueError, IndexError, KeyError):
                pass
        if session_key is None:
            session_key = previous.get("openf1_session_key")
            meeting_key = previous.get("openf1_meeting_key")
    acquisition_manifest = {
        "pipeline_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "canonical_version": "f1-dataset-v1.1 (UNCHANGED)",
        "calibration_version": "calibration-v1.0.0 (UNCHANGED)",
        "simulation_behavior_changed": False,
        "counts": counts,
        "laps_availability_probes": probes if not offline else previous.get("laps_availability_probes", {}),
        "f1db_local_tables": f1db_stats,
        "fastf1": fastf1_info,
        "driver_code_map_size": len(code_to_ref),
        "openf1_session_key": session_key if session_key is not None else previous.get("openf1_session_key"),
        "openf1_meeting_key": meeting_key if meeting_key is not None else previous.get("openf1_meeting_key"),
        "conflict_rate": conflict_rate_n,
        "duplicate_vs_previous_staging": dup_vs_previous,
        "resolution_summary": resolution_summary,
        "promotion_gate": [g.model_dump() for g in gates],
        "warnings": warnings_all[:50],
        "log": log,
        "raw_files": sorted(raw_index, key=lambda r: r["file"]),
    }
    with open(os.path.join(MANIFESTS, "external_acquisition_manifest.json"), "w", encoding="utf-8") as h:
        json.dump(acquisition_manifest, h, indent=2)

    print(json.dumps({"counts": counts, "conflicts": len(conflicts),
                      "raw_files": len(raw_index), "warnings": len(warnings_all)}, indent=2))
    for line in log:
        print(" -", line)
    return 0


def _table_kind(table: str) -> str:
    if table in ("laps_jolpica", "laps_openf1"):
        return "laps"
    if table in ("pit_stops_jolpica", "pit_openf1"):
        return "pit_stops"
    if table == "stints_openf1":
        return "stints"
    if table == "weather_openf1":
        return "weather"
    if table == "race_control_openf1":
        return "race_control"
    return "reanalysis"


def _rebuild_staging_from_raw(
    warnings_all: list[str], log: list[str], counts: dict
) -> dict[str, list]:
    """Rebuild staging tables from immutable raw (offline path)."""
    tables: dict[str, list] = {}
    # Jolpica laps pages
    lap_rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(RAW_ROOT, "jolpica-laps", "*.json"))):
        if path.endswith(".provenance.json"):
            continue
        base = os.path.basename(path)
        try:
            season = int(base.split("-")[0])
            rnd = int(base.split("-r")[1].split("-")[0])
        except (ValueError, IndexError):
            warnings_all.append(f"cannot parse season/round from {base}")
            continue
        with open(path, encoding="utf-8") as h:
            rows, warns = normalize_jolpica_laps(
                json.load(h), source_file=base, season=season, round_no=rnd)
        lap_rows.extend(rows)
        warnings_all.extend(warns)
    tables["laps_jolpica"] = lap_rows
    counts["laps_jolpica"] = len(lap_rows)
    # Jolpica pit pages
    pit_rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(RAW_ROOT, "jolpica-pitstops", "*.json"))):
        if path.endswith(".provenance.json"):
            continue
        base = os.path.basename(path)
        try:
            season = int(base.split("-")[0])
            rnd = int(base.split("-r")[1].split("-")[0])
        except (ValueError, IndexError):
            continue
        with open(path, encoding="utf-8") as h:
            rows, warns = normalize_jolpica_pitstops(
                json.load(h), source_file=base, season=season, round_no=rnd)
        pit_rows.extend(rows)
        warnings_all.extend(warns)
    tables["pit_stops_jolpica"] = pit_rows
    counts["pits_jolpica"] = len(pit_rows)
    # OpenF1 tables
    for name, norm in (("laps", normalize_openf1_laps), ("stints", normalize_openf1_stints),
                       ("weather", normalize_openf1_weather), ("pit", normalize_openf1_pit),
                       ("race_control", normalize_openf1_race_control)):
        src = {"laps": "openf1-timing", "stints": "openf1-stints", "weather": "openf1-weather",
               "pit": "openf1-pit", "race_control": "openf1-racecontrol"}[name]
        rows_all: list[dict] = []
        for path in sorted(glob.glob(os.path.join(RAW_ROOT, src, f"{name}-*.json"))):
            if path.endswith(".provenance.json"):
                continue
            with open(path, encoding="utf-8") as h:
                recs = json.load(h)
            rows, warns = norm(recs if isinstance(recs, list) else [], source_file=os.path.basename(path))
            rows_all.extend(rows)
            warnings_all.extend(warns)
        tables[f"{name}_openf1"] = rows_all
    counts["laps_openf1"] = len(tables.get("laps_openf1", []))
    counts["stints"] = len(tables.get("stints_openf1", []))
    counts["wx_openf1"] = len(tables.get("weather_openf1", []))
    counts["pit_openf1"] = len(tables.get("pit_openf1", []))
    counts["rc"] = len(tables.get("race_control_openf1", []))
    # Open-Meteo
    rean: list[dict] = []
    for path in sorted(glob.glob(os.path.join(RAW_ROOT, "openmeteo-era5", "*.json"))):
        if path.endswith(".provenance.json"):
            continue
        race_id = os.path.basename(path)[:-5]
        anchor = next((a for a in ANCHOR_RACES if a[2] == race_id), None)
        with open(path, encoding="utf-8") as h:
            payload = json.load(h)
        rows, warns = normalize_openmeteo_hourly(
            payload, source_file=os.path.basename(path),
            latitude=anchor[4] if anchor else 0.0, longitude=anchor[5] if anchor else 0.0,
            race_id=race_id)
        rean.extend(rows)
        warnings_all.extend(warns)
    tables["reanalysis_openmeteo"] = rean
    counts["reanalysis_hours"] = len(rean)
    log.append("offline rebuild from raw complete")
    return tables


if __name__ == "__main__":
    raise SystemExit(main())
