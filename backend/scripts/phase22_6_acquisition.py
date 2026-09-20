"""Phase 22.6 resumable deep-backfill runner.

Usage (from backend/):
    python scripts/phase22_6_acquisition.py --dry-run
    python scripts/phase22_6_acquisition.py --pitstops-only
    python scripts/phase22_6_acquisition.py --laps-only --start 1996 --end 2005
    python scripts/phase22_6_acquisition.py --resume
    python scripts/phase22_6_acquisition.py --openf1-only
    python scripts/phase22_6_acquisition.py --weather-only
    python scripts/phase22_6_acquisition.py --race-control-only

Never re-downloads verified immutable raw. Checkpoint:
data/manifests/checkpoint_phase22_6.json. Manifest:
data/manifests/phase22_6_acquisition_manifest.json.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.external.checksums import sha256_bytes, sha256_file, write_sidecar  # noqa: E402
from app.data.external.download import RateLimiter  # noqa: E402
from app.data.provenance import utc_now_iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_JOLPICA = os.path.join(ROOT, "data", "raw", "jolpica")
RAW_OPENF1 = os.path.join(ROOT, "data", "raw", "openf1")
RAW_ERA5 = os.path.join(ROOT, "data", "raw", "era5")
CHECKPOINT = os.path.join(ROOT, "data", "manifests", "checkpoint_phase22_6.json")
MANIFEST = os.path.join(ROOT, "data", "manifests", "phase22_6_acquisition_manifest.json")

JOLPICA = "https://api.jolpi.ca/ergast/f1"
OPENF1 = "https://api.openf1.org/v1"
OPENMETEO = "https://archive-api.open-meteo.com/v1/archive"
LAPS_MIN_SEASON = 1996
PITS_MIN_SEASON = 2011
OPENF1_MIN_SEASON = 2023

OPENF1_RACE_ENDPOINTS = ["laps", "stints", "weather", "pit", "race_control",
                         "position", "overtakes", "team_radio", "session_result",
                         "drivers", "intervals"]
OPENF1_RC_ONLY = ["race_control"]

LIC_JOLPICA = "CC BY-SA (Ergast heritage) / provider terms"
LIC_OPENF1 = "OpenF1 terms (historical free)"
LIC_ERA5 = "CC BY 4.0 (ECMWF/Copernicus via Open-Meteo)"


def http_bytes(url: str, timeout: float = 40.0) -> bytes:
    """GET raw bytes with project User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/22.6"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, encoding="utf-8") as h:
            return json.load(h)
    return {"completed": [], "failed": {}, "stats": {}}


def save_checkpoint(state: dict) -> None:
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(state, h, indent=1, sort_keys=True)
    os.replace(tmp, CHECKPOINT)


def schedule() -> list[dict]:
    """Canonical season/round/race/date rows sorted chronologically."""
    with open(os.path.join(ROOT, "data", "canonical", "races.json"), encoding="utf-8") as h:
        races = json.load(h)
    rows = [{"season": int(r["season_id"]), "round": int(r["round"]),
             "race_id": r["race_id"], "date": r.get("date", ""),
             "circuit_id": r.get("circuit_id", "")} for r in races]
    return sorted(rows, key=lambda r: (r["season"], r["round"]))


def circuit_coords() -> dict[str, tuple[float, float]]:
    """circuit_id -> (lat, lon) from local f1db circuits CSV (no network)."""
    out: dict[str, tuple[float, float]] = {}
    for path in glob.glob(os.path.join(ROOT, "data", "raw", "github", "f1db",
                                       "v2026.13.0", "extracted-v2026.13.0",
                                       "f1db-circuits.csv")):
        with open(path, encoding="utf-8", errors="replace") as h:
            for row in csv.DictReader(h):
                try:
                    out[str(row["id"])] = (float(row["latitude"]), float(row["longitude"]))
                except (ValueError, TypeError, KeyError):
                    continue
    return out


def verified(path: str) -> bool:
    """True when a raw file exists with a matching sha256 sidecar."""
    side = path + ".provenance.json"
    if not (os.path.exists(path) and os.path.exists(side)):
        return False
    with open(side, encoding="utf-8") as h:
        meta = json.load(h)
    return meta.get("sha256") == sha256_file(path)


def store_raw(path: str, payload: bytes, url: str, lic: str, task: str) -> bool:
    """Write raw + sidecar. Returns True when newly written."""
    if verified(path):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as h:
        h.write(payload)
    write_sidecar(path, source_id=task.split(":")[0], source_url=url, license=lic,
                  download_timestamp=utc_now_iso(),
                  extra={"task": task, "sha256_bytes": sha256_bytes(payload)})
    return True


def fetch(url: str, limiter: RateLimiter, tries: int = 5) -> bytes:
    """GET with backoff; honors 429 Retry-After; raises FetchFailed."""
    last: Exception | None = None
    for attempt in range(tries):
        limiter.wait()
        try:
            return http_bytes(url)
        except urllib.error.HTTPError as exc:  # noqa: PERF401
            last = exc
            if exc.code == 404:
                raise FetchFailed(f"404 {url}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait = float(retry_after) if retry_after else 2.0 * (attempt + 1)
            time.sleep(min(wait, 60.0))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise FetchFailed(f"failed {url}: {last}")


class FetchFailed(RuntimeError):
    """Retrieval failure (404, persistent 429/5xx, network)."""


# ---------------------------------------------------------------- tasks ---


def jolpica_pages(base: str, task: str, outdir: str, stem: str, lic: str,
                  limiter: RateLimiter, state: dict, stats: dict) -> None:
    """Fetch all pages of a Jolpica list endpoint into outdir (resumable)."""
    offset = 0
    total: int | None = None
    while True:
        page_path = os.path.join(outdir, f"{stem}-offset{offset}.json")
        url = f"{base}?limit=100&offset={offset}"
        if verified(page_path):
            with open(page_path, encoding="utf-8") as h:
                payload = json.load(h)
            stats["reused_files"] += 1
        else:
            raw = fetch(url, limiter)
            payload = json.loads(raw.decode("utf-8"))
            if "MRData" not in payload:
                raise FetchFailed(f"invalid Jolpica payload (no MRData): {url}")
            store_raw(page_path, raw, url, lic, task)
            stats["downloaded_files"] += 1
            stats["downloaded_bytes"] += len(raw)
        try:
            mr = payload.get("MRData", {})
            total = int(mr.get("total", 0))
        except (ValueError, TypeError):
            total = 0
        offset += 100
        if total is None or offset >= total or total == 0 or offset > 3000:
            break
    stats["rows_total"] += total or 0


def openf1_endpoint(endpoint: str, session_key: int, task: str,
                    limiter: RateLimiter, state: dict, stats: dict) -> None:
    """Fetch one OpenF1 endpoint for one session (resumable)."""
    outdir = os.path.join(RAW_OPENF1, endpoint)
    path = os.path.join(outdir, f"{session_key}.json")
    url = f"{OPENF1}/{endpoint}?session_key={session_key}"
    if verified(path):
        stats["reused_files"] += 1
        return
    raw = fetch(url, limiter)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, list):
        raise FetchFailed(f"invalid OpenF1 payload (not a list): {url}")
    n = len(payload)
    store_raw(path, raw, url, LIC_OPENF1, task)
    stats["downloaded_files"] += 1
    stats["downloaded_bytes"] += len(raw)
    stats["rows_total"] += n


def era5_race(race_id: str, date: str, lat: float, lon: float, task: str,
              limiter: RateLimiter, stats: dict) -> None:
    """Fetch race-day hourly ERA5 for one race (resumable)."""
    path = os.path.join(RAW_ERA5, f"{race_id}.json")
    url = (f"{OPENMETEO}?latitude={lat}&longitude={lon}&start_date={date}"
           f"&end_date={date}&hourly=temperature_2m,relative_humidity_2m,"
           f"precipitation,pressure_msl,wind_speed_10m,wind_direction_10m")
    if verified(path):
        stats["reused_files"] += 1
        return
    raw = fetch(url, limiter)
    try:
        payload = json.loads(raw.decode("utf-8"))
        times = payload["hourly"]["time"]
        if not times:
            raise ValueError("empty hourly series")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise FetchFailed(f"invalid ERA5 payload {url}: {exc}") from exc
    store_raw(path, raw, url, LIC_ERA5, task)
    stats["downloaded_files"] += 1
    stats["downloaded_bytes"] += len(raw)
    try:
        stats["rows_total"] += len(json.loads(raw.decode("utf-8"))["hourly"]["time"])
    except (KeyError, TypeError, ValueError):
        pass


def openf1_race_sessions(year: int, limiter: RateLimiter) -> list[dict]:
    """Discover Race session_keys for a year (cached raw)."""
    path = os.path.join(RAW_OPENF1, "sessions", f"{year}.json")
    url = f"{OPENF1}/sessions?year={year}"
    if not verified(path):
        raw = fetch(url, limiter)
        store_raw(path, raw, url, LIC_OPENF1, f"openf1:sessions:{year}")
    with open(path, encoding="utf-8") as h:
        sessions = json.load(h)
    return [s for s in sessions if s.get("session_name") == "Race"
            and not s.get("is_cancelled")]


# ------------------------------------------------------------------ main ---


def plan_tasks(args: argparse.Namespace) -> list[tuple[str, dict]]:
    """Enumerate (task_id, params) in deterministic order."""
    sched = schedule()
    coords = circuit_coords()
    tasks: list[tuple[str, dict]] = []
    want_laps = args.laps_only or not any([args.pitstops_only, args.openf1_only,
                                           args.weather_only, args.race_control_only])
    want_pits = args.pitstops_only or not any([args.laps_only, args.openf1_only,
                                               args.weather_only, args.race_control_only])
    want_openf1 = args.openf1_only or args.race_control_only or not any(
        [args.laps_only, args.pitstops_only, args.weather_only])
    want_weather = args.weather_only or not any(
        [args.laps_only, args.pitstops_only, args.openf1_only, args.race_control_only])
    today = utc_now_iso()[:10]
    for row in sched:
        s = row["season"]
        if not (args.start <= s <= args.end):
            continue
        if want_laps and s >= LAPS_MIN_SEASON:
            tasks.append((f"jlap:{s}:{row['round']}", {"kind": "jlaps", **row}))
        if want_pits and s >= PITS_MIN_SEASON:
            tasks.append((f"jpit:{s}:{row['round']}", {"kind": "jpits", **row}))
        if want_weather and row["date"] and row["date"] < today and s >= 1950:
            latlon = coords.get(row["circuit_id"])
            if latlon:
                tasks.append((f"era5:{row['race_id']}",
                              {"kind": "era5", "lat": latlon[0], "lon": latlon[1], **row}))
    if want_openf1:
        for year in range(max(args.start, OPENF1_MIN_SEASON), args.end + 1):
            endpoints = OPENF1_RC_ONLY if args.race_control_only and not args.openf1_only \
                else OPENF1_RACE_ENDPOINTS
            tasks.append((f"ofdisc:{year}", {"kind": "ofdisc", "year": year,
                                             "endpoints": endpoints}))
    return tasks


def run_task(task: str, params: dict, limiter: RateLimiter,
             state: dict, stats: dict) -> None:
    """Execute one task; raises FetchFailed / records missing."""
    kind = params["kind"]
    if kind == "jlaps":
        outdir = os.path.join(RAW_JOLPICA, "laps", str(params["season"]), str(params["round"]))
        jolpica_pages(f"{JOLPICA}/{params['season']}/{params['round']}/laps.json",
                      task, outdir, "laps", LIC_JOLPICA, limiter, state, stats)
    elif kind == "jpits":
        outdir = os.path.join(RAW_JOLPICA, "pitstops", str(params["season"]), str(params["round"]))
        jolpica_pages(f"{JOLPICA}/{params['season']}/{params['round']}/pitstops.json",
                      task, outdir, "pitstops", LIC_JOLPICA, limiter, state, stats)
    elif kind == "ofdisc":
        sessions = openf1_race_sessions(params["year"], limiter)
        stats["openf1_sessions"] = stats.get("openf1_sessions", 0) + len(sessions)
        today = utc_now_iso()[:10]
        for s in sessions:
            if str(s.get("date_start", ""))[:10] > today:
                stats["future_deferred"] = stats.get("future_deferred", 0) + 1
                continue  # scheduled but not yet run: leave pending for future backfills
            for ep in params["endpoints"]:
                subtask = f"of:{ep}:{s['session_key']}"
                if subtask in state["completed"] or subtask + ":missing" in state["completed"]:
                    continue
                try:
                    openf1_endpoint(ep, int(s["session_key"]), subtask, limiter, state, stats)
                    state["completed"].append(subtask)
                except FetchFailed as exc:
                    # One missing endpoint must not abort the whole year.
                    stats["missing"] = stats.get("missing", 0) + 1
                    state.setdefault("missing_tasks", []).append(
                        {"task": subtask, "reason": str(exc)[:160]})
                    state["completed"].append(subtask + ":missing")
                    print(f"missing endpoint: {subtask}")
    elif kind == "era5":
        era5_race(params["race_id"], params["date"], params["lat"], params["lon"],
                  task, limiter, stats)


def main() -> int:
    """Entry point."""
    ap = argparse.ArgumentParser(description="Phase 22.6 deep backfill (resumable)")
    ap.add_argument("--start", type=int, default=1996)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--laps-only", action="store_true")
    ap.add_argument("--pitstops-only", action="store_true")
    ap.add_argument("--openf1-only", action="store_true")
    ap.add_argument("--weather-only", action="store_true")
    ap.add_argument("--race-control-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rate", type=float, default=1.2,
                    help="min seconds between requests")
    ap.add_argument("--max-tasks", type=int, default=0,
                    help="stop after N new tasks (0 = all)")
    args = ap.parse_args()

    state = load_checkpoint()
    done = set(state["completed"])
    limiter = RateLimiter(min_interval_seconds=args.rate)
    stats = {"downloaded_files": 0, "reused_files": 0, "downloaded_bytes": 0,
             "rows_total": 0, "failed": 0, "missing": 0}
    if args.resume:
        print(f"resuming: {len(done)} tasks already complete")

    tasks = plan_tasks(args)
    pending = [(t, p) for t, p in tasks if t not in done]
    print(f"tasks: {len(tasks)} total, {len(pending)} pending, "
          f"seasons {args.start}-{args.end}")
    if args.dry_run:
        est_req = sum(12 if p["kind"] == "jlaps" else 2 if p["kind"] == "jpits"
                      else 11 if p["kind"] == "ofdisc" else 1 for _, p in pending)
        print(f"dry-run estimate: ~{est_req} requests, "
              f"~{est_req * args.rate / 60:.0f} min at {args.rate}s spacing")
        return 0

    new_tasks = 0
    for task, params in pending:
        if args.max_tasks and new_tasks >= args.max_tasks:
            print(f"max-tasks {args.max_tasks} reached; checkpoint saved, resume later")
            break
        try:
            run_task(task, params, limiter, state, stats)
            state["completed"].append(task)
            new_tasks += 1
        except FetchFailed as exc:
            message = str(exc)
            if "404" in message:
                stats["missing"] += 1
                state["completed"].append(task)  # 404 = definitively absent; do not retry
                print(f"missing: {task}")
            else:
                stats["failed"] += 1
                state["failed"][task] = message[:200]
                print(f"FAILED (will retry next resume): {task}: {message[:120]}")
        if new_tasks % 5 == 0 or stats["failed"] > 0:
            save_checkpoint(state)
            print(f"progress: {new_tasks} tasks, "
                  f"dl={stats['downloaded_files']} reused={stats['reused_files']} "
                  f"failed={stats['failed']}", flush=True)
    save_checkpoint(state)

    manifest = {
        "pipeline": "phase22_6_acquisition",
        "generated_at": utc_now_iso(),
        "seasons": [args.start, args.end],
        "tasks_total": len(tasks),
        "tasks_completed": len(state["completed"]),
        "tasks_failed": state["failed"],
        "stats": stats,
        "rate_seconds": args.rate,
        "canonicalization_status": "RAW_ONLY (canonicalize separately)",
    }
    with open(MANIFEST, "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, sort_keys=True)
    print(json.dumps({"new_tasks": new_tasks, **stats}, indent=1))
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
