#!/usr/bin/env python3
"""Accelerated parallel Jolpica acquisition - 3 workers."""

import json
import time
import random
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path("C:/Users/gokha/Desktop/f1 simülasyonu/backend")
RAW_LAPS = ROOT / "data" / "raw" / "jolpica" / "laps"
MANIFEST_FILE = ROOT / "data" / "manifests" / "phase22_7_laps_acquisition_manifest.json"

BASE_URL = "https://api.jolpi.ca/ergast/f1"
PAGE_SIZE = 500
RATE_SECONDS = 0.6
MAX_WORKERS = 3
MAX_RETRIES = 3

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fetch_with_retry(url: str):
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/phase22.7-fast"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read(), resp.status, None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = max(4.0, 1.0 * (1.8 ** attempt)) + random.uniform(0, 1.5)
                print(f"  429 wait {wait:.1f}s")
                time.sleep(wait)
                if attempt >= 2:
                    time.sleep(5)
                continue
            elif e.code >= 500:
                time.sleep(1.0 * (1.8 ** attempt) + random.uniform(0, 0.5))
                continue
            else:
                return None, e.code, f"HTTP {e.code}"
        except Exception as e:
            time.sleep(1.0 * (1.8 ** attempt))
            if attempt == MAX_RETRIES:
                return None, None, str(e)
    return None, None, "max retries"

def fetch_race(season: int, round_num: int):
    time.sleep(RATE_SECONDS + random.uniform(0, 0.3))
    all_laps = []
    offset = 0
    total_bytes = 0
    pages = 0
    last_url = ""
    while True:
        url = f"{BASE_URL}/{season}/{round_num}/laps.json?limit={PAGE_SIZE}&offset={offset}"
        last_url = url
        data, status, err = fetch_with_retry(url)
        if err:
            return {"season": season, "round": round_num, "status": "failed", "url": url, "http_status": status, "error": err, "timestamp": datetime.now(timezone.utc).isoformat()}
        total_bytes += len(data)
        pages += 1
        payload = json.loads(data.decode())
        # validate
        try:
            race = payload["MRData"]["RaceTable"]["Races"][0]
            laps = race.get("Laps", [])
            if not laps:
                return {"season": season, "round": round_num, "status": "quarantined", "url": url, "error": "no_laps", "timestamp": datetime.now(timezone.utc).isoformat()}
            all_laps.extend(laps)
            total = int(payload["MRData"].get("total", "0"))
            if offset + PAGE_SIZE >= total:
                break
            offset += PAGE_SIZE
            time.sleep(RATE_SECONDS + random.uniform(0, 0.2))
        except Exception as e:
            return {"season": season, "round": round_num, "status": "quarantined", "url": url, "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
    # save
    race_dir = RAW_LAPS / str(season) / str(round_num)
    race_dir.mkdir(parents=True, exist_ok=True)
    combined = {"MRData": {"RaceTable": {"Races": [{"season": str(season), "round": str(round_num), "Laps": all_laps}]}, "total": str(len(all_laps))}}
    b = json.dumps(combined, separators=(',', ':')).encode()
    fpath = race_dir / "laps-combined.json"
    with open(fpath, 'wb') as f:
        f.write(b)
    sha = compute_sha256(b)
    with open(fpath.with_suffix(fpath.suffix + ".sha256"), 'w') as f:
        f.write(sha)
    prov = {"source": "jolpica", "endpoint": f"/{season}/{round_num}/laps.json", "season": season, "round": round_num, "pages_fetched": pages, "total_laps": len(all_laps), "page_size": PAGE_SIZE, "parser_version": "22.7.0", "sha256": sha, "bytes": len(b), "retrieved_at": datetime.now(timezone.utc).isoformat()}
    with open(fpath.with_suffix(fpath.suffix + ".provenance.json"), 'w') as f:
        json.dump(prov, f, indent=2, sort_keys=True)
    return {"season": season, "round": round_num, "status": "completed", "url": last_url, "http_status": 200, "bytes_downloaded": total_bytes, "pages": pages, "total_laps": len(all_laps), "sha256": sha, "timestamp": datetime.now(timezone.utc).isoformat()}

def load_missing():
    with open(ROOT / "data" / "canonical" / "races.json") as f:
        races = json.load(f)
    acquired = set()
    for sd in RAW_LAPS.iterdir():
        if sd.is_dir() and sd.name.isdigit():
            s = int(sd.name)
            for rd in sd.iterdir():
                if rd.is_dir() and rd.name.isdigit():
                    acquired.add((s, int(rd.name)))
    missing = []
    for r in races:
        s = int(r['season_id']); rnd = int(r['round'])
        if 2002 <= s <= 2026 and (s, rnd) not in acquired:
            missing.append((s, rnd))
    return sorted(missing)

def main():
    missing = load_missing()
    print(f"Missing: {len(missing)}")
    by_s = {}
    for s,r in missing:
        by_s.setdefault(s, []).append(r)
    for s in sorted(by_s):
        print(f" {s}: {by_s[s]}")
    # load existing
    existing = []
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            existing = json.load(f).get("results", [])
    completed_keys = {f"{r['season']}:{r['round']}" for r in existing if r.get('status')=='completed'}
    # Filter.
    todo = [(s,r) for s,r in missing if f"{s}:{r}" not in completed_keys]
    print(f"Todo after manifest filter: {len(todo)}")
    # Also filter by raw existence already handled, so todo is correct.

    results = []
    # Use thread pool
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_to_race = {ex.submit(fetch_race, s, r): (s,r) for s,r in todo}
        done = 0
        for fut in as_completed(future_to_race):
            s,r = future_to_race[fut]
            try:
                res = fut.result()
                results.append(res)
                done += 1
                if res['status']=='completed':
                    print(f"[{done}/{len(todo)}] OK {s} R{r}: {res['total_laps']} laps pages={res['pages']}")
                else:
                    print(f"[{done}/{len(todo)}] FAIL {s} R{r}: {res.get('error')}")
            except Exception as e:
                results.append({"season": s, "round": r, "status": "failed", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()})
                print(f" EXC {s} R{r}: {e}")
            # Save manifest periodically
            if done % 10 == 0:
                all_res = existing + results
                manifest = {
                    "pipeline": "phase22_7_laps_acquisition",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "rate_seconds": RATE_SECONDS,
                    "page_size": PAGE_SIZE,
                    "workers": MAX_WORKERS,
                    "results": all_res,
                    "stats": {
                        "completed": sum(1 for x in all_res if x.get('status')=='completed'),
                        "failed": sum(1 for x in all_res if x.get('status')=='failed'),
                        "quarantined": sum(1 for x in all_res if x.get('status')=='quarantined'),
                        "skipped": 0,
                        "total_laps": sum(x.get('total_laps',0) for x in all_res if x.get('status')=='completed'),
                        "total_bytes": sum(x.get('bytes_downloaded',0) for x in all_res),
                    }
                }
                with open(MANIFEST_FILE, 'w') as f:
                    json.dump(manifest, f, indent=2, sort_keys=True)
                print(f"  -> manifest saved {len(all_res)}")
    # final
    all_res = existing + results
    manifest = {
        "pipeline": "phase22_7_laps_acquisition",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rate_seconds": RATE_SECONDS,
        "page_size": PAGE_SIZE,
        "workers": MAX_WORKERS,
        "results": all_res,
        "stats": {
            "completed": sum(1 for x in all_res if x.get('status')=='completed'),
            "failed": sum(1 for x in all_res if x.get('status')=='failed'),
            "quarantined": sum(1 for x in all_res if x.get('status')=='quarantined'),
            "skipped": 0,
            "total_laps": sum(x.get('total_laps',0) for x in all_res if x.get('status')=='completed'),
            "total_bytes": sum(x.get('bytes_downloaded',0) for x in all_res),
        }
    }
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print("DONE", manifest["stats"])

if __name__ == "__main__":
    main()
