"""Phase 22.7 rate-limit-safe Jolpica laps backfill (2002-2026).

Usage (from backend/):
    python scripts/phase22_7_acquisition.py --dry-run
    python scripts/phase22_7_acquisition.py --laps-only --start 2002 --end 2026 --rate 3 --resume
    python scripts/phase22_7_acquisition.py --laps-only --start 2002 --end 2026 --rate 3 --resume --max-tasks 25

Properties:
  - resumable via data/manifests/checkpoint_phase22_7.json (pre-seeded with the
    99 verified 1996-2001 tasks so immutable raw is never redownloaded)
  - adaptive pacing: starts at --rate, backs off x1.5 (cap 30 s) on 429/5xx
    with jitter, honors Retry-After, decays back toward base on success
  - payload validation BEFORE storage; rejects go to data/raw/quarantine/
  - immutable raw: verified files never overwritten; re-fetched bytes are hash
    compared (DUPLICATE_IDENTICAL vs RAW_CONFLICT, conflict preserved aside)
  - every raw file gets .provenance.json AND .sha256 sidecars with
    retrieved_at/source/endpoint/season/round/http_status/hash/parser version
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.external.checksums import sha256_bytes, sha256_file, write_sidecar  # noqa: E402
from app.data.provenance import utc_now_iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_LAPS = os.path.join(ROOT, "data", "raw", "jolpica", "laps")
QUARANTINE = os.path.join(ROOT, "data", "raw", "quarantine")
CHECKPOINT = os.path.join(ROOT, "data", "manifests", "checkpoint_phase22_7.json")
MANIFEST = os.path.join(ROOT, "data", "manifests", "phase22_7_acquisition_manifest.json")

JOLPICA = "https://api.jolpi.ca/ergast/f1"
PARSER_VERSION = "22.7.0"
LIC_JOLPICA = "CC BY-SA (Ergast heritage) / provider terms"
MAX_INTERVAL = 30.0


class FetchFailed(RuntimeError):
    """Retrieval failure (persistent 429/5xx, network, timeout)."""


class MissingAtSource(RuntimeError):
    """Endpoint answered but holds no lap data for this race (total=0 / no Races)."""


class Quarantined(RuntimeError):
    """Payload failed validation and was preserved under quarantine/."""


class AdaptivePacer:
    """Minimum-interval gate with backoff on throttling and slow recovery."""

    def __init__(self, base: float) -> None:
        self.base = base
        self.current = base
        self._last: float = 0.0
        self._successes = 0

    def wait(self) -> None:
        now = time.monotonic()
        gap = now - self._last
        delay = self.current + random.uniform(0, 0.5 * self.current)  # jitter
        if gap < delay:
            time.sleep(delay - gap)
        self._last = time.monotonic()

    def on_success(self) -> None:
        self._successes += 1
        if self._successes >= 20 and self.current > self.base:
            self.current = max(self.base, self.current * 0.9)
            self._successes = 0

    def on_throttle(self) -> None:
        self.current = min(MAX_INTERVAL, self.current * 1.5)
        self._successes = 0


def http_get(url: str, timeout: float = 45.0) -> tuple[bytes, int, dict]:
    """GET raw bytes; returns (body, status, headers). Raises HTTPError as-is."""
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/22.7"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read(), getattr(resp, "status", 200), dict(resp.headers.items())


def validate_laps_payload(raw: bytes, url: str) -> tuple[dict, int]:
    """Validate a Jolpica laps page. Returns (payload, total).

    Raises MissingAtSource for valid-but-empty (total=0 / Races=[]) and
    Quarantined for malformed/error payloads (already preserved aside).
    """
    text_head = raw[:200].decode("utf-8", errors="replace").strip().lower()
    if text_head.startswith("<"):
        raise Quarantined(_quarantine(raw, url, "html_error_page"))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Quarantined(_quarantine(raw, url, f"malformed_json: {exc}"[:160])) from exc
    if not isinstance(payload, dict) or "MRData" not in payload:
        raise Quarantined(_quarantine(raw, url, "unexpected_schema_no_MRData"))
    mr = payload.get("MRData") or {}
    if isinstance(mr, dict) and "error" in mr:
        raise Quarantined(_quarantine(raw, url, f"api_error_object: {str(mr.get('error'))[:120]}"))
    try:
        total = int(mr.get("total", 0))
    except (ValueError, TypeError):
        raise Quarantined(_quarantine(raw, url, "unparseable_total")) from None
    races = (mr.get("RaceTable") or {}).get("Races", [])
    if total == 0 or not races:
        raise MissingAtSource(f"no lap data at source (total={total}, races={len(races)}): {url}")
    return payload, total


def _quarantine(raw: bytes, url: str, reason: str) -> str:
    """Preserve a rejected payload; return the quarantine path."""
    os.makedirs(QUARANTINE, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()[:16]
    stamp = utc_now_iso().replace(":", "").replace("+", "Z")
    name = f"jolpica-laps-{stamp}-{digest}.bin"
    path = os.path.join(QUARANTINE, name)
    with open(path, "wb") as h:
        h.write(raw)
    meta = {"reason": reason, "sha256": hashlib.sha256(raw).hexdigest(),
            "endpoint": url, "retrieved_at": utc_now_iso(), "bytes": len(raw)}
    with open(path + ".reason.json", "w", encoding="utf-8") as h:
        json.dump(meta, h, indent=2, sort_keys=True)
    return path


def verified(path: str) -> bool:
    side = path + ".provenance.json"
    if not (os.path.exists(path) and os.path.exists(side)):
        return False
    try:
        with open(side, encoding="utf-8") as h:
            meta = json.load(h)
    except (ValueError, OSError):
        return False
    return meta.get("sha256") == sha256_file(path)


def adopted_combined(season: int, rnd: int) -> bool:
    """True when a verified combined raw file already covers this race.

    Adopted (never redownloaded): the combined layout is an equivalent
    immutable raw source; canonicalization uses exactly one source per race.
    """
    path = os.path.join(RAW_LAPS, str(season), str(rnd), "laps-combined.json")
    return verified(path)


def store_verified(path: str, payload: bytes, url: str, task: str,
                   season: int, rnd: int, status: int, stats: dict) -> str:
    """Store raw immutably with both sidecars. Returns DUPLICATE_IDENTICAL /
    RAW_CONFLICT / STORED_NEW. Never overwrites differing verified content."""
    digest = sha256_bytes(payload)
    if os.path.exists(path) and not verified(path):
        with open(path, "rb") as h:
            old = h.read()
        if sha256_bytes(old) == digest:
            stats["duplicate_identical"] = stats.get("duplicate_identical", 0) + 1
        else:
            stats["raw_conflicts"] = stats.get("raw_conflicts", 0) + 1
            stamp = utc_now_iso().replace(":", "").replace("+", "Z")
            cpath = f"{path}.conflict-{stamp}"
            with open(cpath, "wb") as h:
                h.write(payload)
            return "RAW_CONFLICT"
    if verified(path):
        stats["duplicate_identical"] = stats.get("duplicate_identical", 0) + 1
        return "DUPLICATE_IDENTICAL"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as h:
        h.write(payload)
    write_sidecar(path, source_id="jolpica-laps", source_url=url, license=LIC_JOLPICA,
                  download_timestamp=utc_now_iso(),
                  source_version="api.jolpi.ca",
                  extra={"task": task, "season": season, "round": rnd,
                         "http_status": status, "parser_version": PARSER_VERSION,
                         "retrieved_at": utc_now_iso(), "endpoint": url,
                         "sha256_bytes": digest})
    with open(path + ".sha256", "w", encoding="utf-8") as h:
        h.write(digest + "\n")
    return "STORED_NEW"


def fetch(url: str, pacer: AdaptivePacer, stats: dict, tries: int = 6,
          timeout: float = 45.0) -> tuple[bytes, int]:
    """GET with adaptive backoff; honors Retry-After; raises FetchFailed."""
    last: Exception | None = None
    for attempt in range(tries):
        pacer.wait()
        try:
            raw, status, headers = http_get(url, timeout=timeout)
            if status == 429 or status >= 500:
                raise urllib.error.HTTPError(url, status, "throttled", headers, None)
            pacer.on_success()
            return raw, status
        except urllib.error.HTTPError as exc:
            last = exc
            stats["rate_limits"] = stats.get("rate_limits", 0) + (1 if exc.code == 429 else 0)
            if exc.code == 404:
                raise FetchFailed(f"404 {url}") from exc
            pacer.on_throttle()
            retry_after = None
            try:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
            except Exception:  # noqa: BLE001
                retry_after = None
            try:
                wait = float(retry_after) if retry_after else pacer.current * (attempt + 1)
            except (ValueError, TypeError):
                wait = pacer.current * (attempt + 1)
            print(f"throttle/backoff: HTTP {exc.code}, sleeping {min(wait, 120.0):.1f}s "
                  f"(pacer now {pacer.current:.1f}s)", flush=True)
            time.sleep(min(wait, 120.0))
        except Exception as exc:  # noqa: BLE001 - timeouts, resets
            last = exc
            pacer.on_throttle()
            time.sleep(min(pacer.current * (attempt + 1), 120.0))
    raise FetchFailed(f"failed {url}: {last}")


def schedule(start: int, end: int) -> list[dict]:
    with open(os.path.join(ROOT, "data", "canonical", "races.json"), encoding="utf-8") as h:
        races = json.load(h)
    rows = [{"season": int(r["season_id"]), "round": int(r["round"]),
             "race_id": r["race_id"], "date": r.get("date", "")} for r in races
            if start <= int(r["season_id"]) <= end]
    return sorted(rows, key=lambda r: (r["season"], r["round"]))


def seed_checkpoint(state: dict) -> dict:
    """Pre-seed verified 1996-2001 laps tasks so they are never redownloaded."""
    done = set(state.get("completed", []))
    added = 0
    laps_root = os.path.join(ROOT, "data", "raw", "jolpica", "laps")
    for season in range(1996, 2002):
        sdir = os.path.join(laps_root, str(season))
        if not os.path.isdir(sdir):
            continue
        for rnd in os.listdir(sdir):
            rdir = os.path.join(sdir, rnd)
            if not os.path.isdir(rdir):
                continue
            pages = [f for f in os.listdir(rdir)
                     if f.endswith(".json") and not f.endswith(".provenance.json")]
            if not pages:
                continue
            ok = all(verified(os.path.join(rdir, f)) for f in pages)
            if ok:
                task = f"jlap:{season}:{int(rnd)}"
                if task not in done:
                    state.setdefault("completed", []).append(task)
                    added += 1
    if added:
        print(f"pre-seed: {added} verified 1996-2001 tasks marked complete (never redownloaded)")
    return state


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, encoding="utf-8") as h:
            return json.load(h)
    return {"completed": [], "failed": {}, "missing_tasks": [], "quarantined": [],
            "conflicts": [], "stats": {}}


def save_checkpoint(state: dict) -> None:
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(state, h, indent=1, sort_keys=True)
    os.replace(tmp, CHECKPOINT)


def fetch_race_laps(season: int, rnd: int, task: str, pacer: AdaptivePacer,
                    stats: dict, state: dict) -> None:
    """Fetch all pages of one race's laps endpoint (resumable per page)."""
    outdir = os.path.join(RAW_LAPS, str(season), str(rnd))
    base = f"{JOLPICA}/{season}/{rnd}/laps.json"
    offset = 0
    total: int | None = None
    while True:
        page_path = os.path.join(outdir, f"laps-offset{offset}.json")
        url = f"{base}?limit=100&offset={offset}"
        if verified(page_path):
            with open(page_path, encoding="utf-8") as h:
                payload = json.load(h)
            try:
                total = int(payload.get("MRData", {}).get("total", 0))
            except (ValueError, TypeError):
                total = 0
            stats["reused_files"] = stats.get("reused_files", 0) + 1
            stats["duplicate_identical"] = stats.get("duplicate_identical", 0) + 1
        else:
            raw, status = fetch(url, pacer, stats)
            try:
                payload, total = validate_laps_payload(raw, url)
            except MissingAtSource as exc:
                if offset == 0:
                    stats["missing"] = stats.get("missing", 0) + 1
                    state.setdefault("missing_tasks", []).append(
                        {"task": task, "reason": str(exc)[:160]})
                    print(f"missing at source: {task}")
                    return
                raise FetchFailed(f"mid-pagination empty page: {url}") from exc
            except Quarantined as exc:
                stats["quarantined"] = stats.get("quarantined", 0) + 1
                state.setdefault("quarantined", []).append(
                    {"task": task, "url": url, "path": str(exc)[:200]})
                raise FetchFailed(f"quarantined payload: {url}") from exc
            outcome = store_verified(page_path, raw, url, task, season, rnd, status, stats)
            if outcome == "RAW_CONFLICT":
                state.setdefault("conflicts", []).append({"task": task, "url": url})
                print(f"RAW_CONFLICT preserved aside (original kept): {page_path}")
            else:
                stats["downloaded_files"] = stats.get("downloaded_files", 0) + 1
                stats["downloaded_bytes"] = stats.get("downloaded_bytes", 0) + len(raw)
        offset += 100
        if total is None or offset >= total or total == 0 or offset > 3000:
            break
    stats["rows_total"] = stats.get("rows_total", 0) + (total or 0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 22.7 laps backfill (resumable)")
    ap.add_argument("--start", type=int, default=2002)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--laps-only", action="store_true")
    ap.add_argument("--pitstops-only", action="store_true")
    ap.add_argument("--openf1-only", action="store_true")
    ap.add_argument("--weather-only", action="store_true")
    ap.add_argument("--race-control-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rate", type=float, default=3.0)
    ap.add_argument("--max-tasks", type=int, default=0)
    args = ap.parse_args()

    state = seed_checkpoint(load_checkpoint())
    done = set(state["completed"])
    pacer = AdaptivePacer(base=args.rate)
    stats = {"downloaded_files": 0, "reused_files": 0, "downloaded_bytes": 0,
             "rows_total": 0, "failed": 0, "missing": 0, "quarantined": 0,
             "duplicate_identical": 0, "raw_conflicts": 0, "rate_limits": 0}
    if args.resume:
        print(f"resuming: {len(done)} tasks already complete")

    sched = schedule(args.start, args.end)
    tasks = [(f"jlap:{r['season']}:{r['round']}", r) for r in sched]
    pending = [(t, p) for t, p in tasks
               if t not in done and not adopted_combined(p["season"], p["round"])]
    n_adopted = len(tasks) - len(pending) - len([t for t, _ in tasks if t in done])
    print(f"tasks: {len(tasks)} total, {len(pending)} pending, seasons {args.start}-{args.end}")
    if n_adopted:
        print(f"adopted: {n_adopted} races already covered by verified combined raw (skipped)")
    if args.dry_run:
        est = len(pending) * 10
        print(f"dry-run estimate: ~{est} requests, ~{est * args.rate / 60:.0f} min at {args.rate}s spacing")
        return 0

    new_tasks = 0
    for task, params in pending:
        if args.max_tasks and new_tasks >= args.max_tasks:
            print(f"max-tasks {args.max_tasks} reached; checkpoint saved, resume later")
            break
        try:
            fetch_race_laps(params["season"], params["round"], task, pacer, stats, state)
            if task in state.get("failed", {}):
                del state["failed"][task]
            state["completed"].append(task)
            new_tasks += 1
        except FetchFailed as exc:
            message = str(exc)
            if message.startswith("404"):
                stats["failed"] = stats.get("failed", 0)  # 404 counted as missing below
                stats["missing"] = stats.get("missing", 0) + 1
                state["completed"].append(task)
                state.setdefault("missing_tasks", []).append({"task": task, "reason": message[:160]})
                print(f"missing: {task}")
            else:
                stats["failed"] = stats.get("failed", 0) + 1
                state["failed"][task] = message[:200]
                print(f"FAILED (will retry next resume): {task}: {message[:120]}", flush=True)
        save_checkpoint(state)
        print(f"progress: {new_tasks} new tasks, dl={stats['downloaded_files']} "
              f"reused={stats['reused_files']} failed={stats['failed']} "
              f"missing={stats['missing']} quar={stats['quarantined']} "
              f"429s={stats['rate_limits']} pacer={pacer.current:.1f}s", flush=True)

    save_checkpoint(state)
    manifest = {
        "pipeline": "phase22_7_acquisition",
        "generated_at": utc_now_iso(),
        "seasons": [args.start, args.end],
        "parser_version": PARSER_VERSION,
        "tasks_total": len(tasks),
        "tasks_completed": len(state["completed"]),
        "tasks_failed": state.get("failed", {}),
        "missing_tasks": state.get("missing_tasks", []),
        "quarantined": state.get("quarantined", []),
        "conflicts": state.get("conflicts", []),
        "stats": stats,
        "rate_seconds": args.rate,
        "final_pacer_seconds": round(pacer.current, 2),
        "canonicalization_status": "RAW_ONLY (canonicalize separately)",
    }
    with open(MANIFEST, "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, sort_keys=True)
    print(json.dumps({"new_tasks": new_tasks, **stats}, indent=1))
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
