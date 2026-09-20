#!/usr/bin/env python3
"""Phase 22.7 - Robust Jolpica Lap Acquisition for 2002-2026.

Features:
- Resumable with checkpointing
- Exponential backoff with jitter
- 429 handling with Retry-After support
- Timeout handling
- Immutable raw storage with SHA256 sidecars
- Payload validation with quarantine
- Provenance tracking
"""

import json
import os
import time
import hashlib
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

ROOT = Path("C:/Users/gokha/Desktop/f1 simülasyonu/backend")
RAW_LAPS = ROOT / "data" / "raw" / "jolpica" / "laps"
QUARANTINE_DIR = ROOT / "data" / "raw" / "quarantine"
CHECKPOINT_FILE = ROOT / "data" / "manifests" / "checkpoint_phase22_7_laps.json"
MANIFEST_FILE = ROOT / "data" / "manifests" / "phase22_7_laps_acquisition_manifest.json"

BASE_URL = "https://api.jolpi.ca/ergast/f1"
RATE_SECONDS = 0.8  # Accelerated - tuned for sustainable rate (was 4.0)
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
PAGE_SIZE = 500  # Larger pages to reduce request count (was 100)

@dataclass
class AcquisitionResult:
    season: int
    round: int
    status: str  # "completed", "failed", "skipped", "quarantined"
    url: str
    http_status: Optional[int] = None
    bytes_downloaded: int = 0
    pages: int = 0
    total_laps: int = 0
    error: Optional[str] = None
    sha256: Optional[str] = None
    timestamp: str = ""

class CheckpointStore:
    def __init__(self, path: Path):
        self.path = path
        self.state: dict[str, str] = {}
        if path.exists():
            with open(path, 'r') as f:
                self.state = json.load(f)

    def get(self, key: str) -> str:
        return self.state.get(key, "pending")

    def set(self, key: str, status: str) -> None:
        self.state[key] = status
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self.state, f, indent=2, sort_keys=True)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"completed": 0, "failed": 0, "skipped": 0, "pending": 0, "quarantined": 0}
        for v in self.state.values():
            counts[v] = counts.get(v, 0) + 1
        return counts

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def write_with_sidecars(filepath: Path, data: bytes, provenance: dict) -> None:
    """Write raw data with .sha256 and .provenance.json sidecars."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Write main file
    with open(filepath, 'wb') as f:
        f.write(data)
    
    # Write SHA256
    sha256 = compute_sha256(data)
    with open(filepath.with_suffix(filepath.suffix + ".sha256"), 'w') as f:
        f.write(sha256)
    
    # Write provenance
    provenance["sha256"] = sha256
    provenance["bytes"] = len(data)
    provenance["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    with open(filepath.with_suffix(filepath.suffix + ".provenance.json"), 'w') as f:
        json.dump(provenance, f, indent=2, sort_keys=True)
    
    return sha256

def validate_payload(payload: dict, url: str) -> tuple[bool, Optional[str]]:
    """Validate Jolpica laps payload. Returns (is_valid, error_reason)."""
    # Check basic structure
    if not isinstance(payload, dict):
        return False, "not_a_dict"
    
    # Check for API error responses
    if "error" in payload or "message" in payload:
        return False, f"api_error: {payload.get('error') or payload.get('message')}"
    
    # Check MRData structure
    mrdata = payload.get("MRData")
    if not mrdata:
        return False, "missing_MRData"
    
    race_table = mrdata.get("RaceTable")
    if not race_table:
        return False, "missing_RaceTable"
    
    races = race_table.get("Races")
    if not races or not isinstance(races, list) or len(races) == 0:
        return False, "no_races_in_response"
    
    race = races[0]
    laps = race.get("Laps")
    if not laps or not isinstance(laps, list):
        return False, "no_laps_in_race"
    
    # Check that laps have timings
    has_timings = False
    for lap in laps:
        timings = lap.get("Timings")
        if timings and isinstance(timings, list) and len(timings) > 0:
            has_timings = True
            break
    
    if not has_timings:
        return False, "no_timings_in_laps"
    
    return True, None

def quarantine_payload(payload: dict, url: str, reason: str, season: int, round_num: int) -> None:
    """Store invalid payload in quarantine directory."""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    fname = f"quarantine_{season}_{round_num}_{timestamp}.json"
    fpath = QUARANTINE_DIR / fname
    
    record = {
        "reason": reason,
        "url": url,
        "season": season,
        "round": round_num,
        "timestamp": timestamp,
        "payload_hash": compute_sha256(json.dumps(payload, sort_keys=True).encode()),
        "payload": payload,
    }
    
    with open(fpath, 'w') as f:
        json.dump(record, f, indent=2, sort_keys=True)

def fetch_with_retry(url: str, max_retries: int = MAX_RETRIES) -> tuple[Optional[bytes], Optional[int], Optional[str]]:
    """Fetch URL with exponential backoff, jitter, and 429 handling. Accelerated."""
    backoff_base = 1.0
    backoff_multiplier = 1.8
    last_exc: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/phase22.7"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                data = response.read()
                return data, response.status, None
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code == 429:
                # Honor Retry-After header
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = float(retry_after) + random.uniform(0, 1)
                    except ValueError:
                        wait = backoff_base * (backoff_multiplier ** attempt) + random.uniform(0, 0.5 * backoff_base)
                else:
                    wait = max(5.0, backoff_base * (backoff_multiplier ** attempt)) + random.uniform(0, 2)
                print(f"  429 Rate limited, waiting {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
                time.sleep(wait)
                # Extra cooldown for persistent 429
                if attempt >= 2:
                    time.sleep(8 + random.uniform(0, 2))
                continue
            elif e.code >= 500:
                # Server error, retry
                wait = backoff_base * (backoff_multiplier ** attempt) + random.uniform(0, 0.5 * backoff_base)
                print(f"  HTTP {e.code}, waiting {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
                time.sleep(wait)
                continue
            else:
                # Client error (404, 400, etc.) - don't retry
                return None, e.code, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            last_exc = e
            wait = backoff_base * (backoff_multiplier ** attempt) + random.uniform(0, 0.5 * backoff_base)
            print(f"  Network error: {e}, waiting {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
            time.sleep(wait)
        except TimeoutError as e:
            last_exc = e
            wait = backoff_base * (backoff_multiplier ** attempt) + random.uniform(0, 0.5 * backoff_base)
            print(f"  Timeout, waiting {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
            time.sleep(wait)
        except Exception as e:
            last_exc = e
            wait = backoff_base * (backoff_multiplier ** attempt) + random.uniform(0, 0.5 * backoff_base)
            print(f"  Unexpected error: {e}, waiting {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
            time.sleep(wait)
    
    return None, None, f"Max retries exceeded: {last_exc}"

def fetch_all_laps_for_race(season: int, round_num: int, checkpoint: CheckpointStore) -> AcquisitionResult:
    """Fetch all laps for a single race with pagination."""
    key = f"jlap:{season}:{round_num}"
    
    # Check checkpoint
    if checkpoint.get(key) == "completed":
        return AcquisitionResult(
            season=season, round=round_num, status="skipped",
            url="", timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    all_laps = []
    total_pages = 0
    total_bytes = 0
    offset = 0
    
    while True:
        # Rate limiting
        time.sleep(RATE_SECONDS + random.uniform(0, 0.5))
        
        url = f"{BASE_URL}/{season}/{round_num}/laps.json?limit={PAGE_SIZE}&offset={offset}"
        print(f"  Fetching {season} R{round_num} offset={offset}...")
        
        data, status, error = fetch_with_retry(url)
        if error:
            checkpoint.set(key, "failed")
            return AcquisitionResult(
                season=season, round=round_num, status="failed",
                url=url, http_status=status, error=error,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        total_bytes += len(data)
        total_pages += 1
        
        try:
            payload = json.loads(data.decode('utf-8'))
        except json.JSONDecodeError as e:
            quarantine_payload({"raw": data.decode('utf-8', errors='replace')}, url, f"invalid_json: {e}", season, round_num)
            checkpoint.set(key, "quarantined")
            return AcquisitionResult(
                season=season, round=round_num, status="quarantined",
                url=url, http_status=status, bytes_downloaded=total_bytes,
                pages=total_pages, error=f"invalid_json: {e}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Validate payload
        is_valid, reason = validate_payload(payload, url)
        if not is_valid:
            quarantine_payload(payload, url, reason, season, round_num)
            checkpoint.set(key, "quarantined")
            return AcquisitionResult(
                season=season, round=round_num, status="quarantined",
                url=url, http_status=status, bytes_downloaded=total_bytes,
                pages=total_pages, error=f"validation_failed: {reason}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Extract laps
        try:
            race = payload["MRData"]["RaceTable"]["Races"][0]
            laps = race.get("Laps", [])
            all_laps.extend(laps)
            
            # Check if more pages
            total = int(payload["MRData"].get("total", "0"))
            if offset + PAGE_SIZE >= total:
                break
            offset += PAGE_SIZE
        except (KeyError, IndexError, ValueError) as e:
            quarantine_payload(payload, url, f"parse_error: {e}", season, round_num)
            checkpoint.set(key, "quarantined")
            return AcquisitionResult(
                season=season, round=round_num, status="quarantined",
                url=url, http_status=status, bytes_downloaded=total_bytes,
                pages=total_pages, error=f"parse_error: {e}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    # Save raw data
    race_dir = RAW_LAPS / str(season) / str(round_num)
    race_dir.mkdir(parents=True, exist_ok=True)
    
    # Combine all pages into one payload for storage
    combined_payload = {
        "MRData": {
            "RaceTable": {
                "Races": [{
                    "season": str(season),
                    "round": str(round_num),
                    "Laps": all_laps
                }]
            },
            "total": str(len(all_laps))
        }
    }
    
    combined_data = json.dumps(combined_payload, separators=(',', ':')).encode('utf-8')
    
    fname = f"laps-combined.json"
    fpath = race_dir / fname
    
    provenance = {
        "source": "jolpica",
        "endpoint": f"/{season}/{round_num}/laps.json",
        "season": season,
        "round": round_num,
        "pages_fetched": total_pages,
        "total_laps": len(all_laps),
        "page_size": PAGE_SIZE,
        "parser_version": "22.7.0",
    }
    
    sha256 = write_with_sidecars(fpath, combined_data, provenance)
    
    checkpoint.set(key, "completed")
    
    return AcquisitionResult(
        season=season, round=round_num, status="completed",
        url=url, http_status=200, bytes_downloaded=total_bytes,
        pages=total_pages, total_laps=len(all_laps),
        sha256=sha256, timestamp=datetime.now(timezone.utc).isoformat()
    )

def load_missing_races() -> list[tuple[int, int]]:
    """Load list of missing races from preflight audit."""
    audit_path = ROOT / "docs" / "phase22_7_preflight_audit.md"
    # We'll just compute it here
    with open(ROOT / "data" / "canonical" / "races.json", 'r') as f:
        races = json.load(f)
    
    # Get raw seasons
    raw_seasons = {}
    for season_dir in RAW_LAPS.iterdir():
        if season_dir.is_dir() and season_dir.name.isdigit():
            season = int(season_dir.name)
            races_raw = []
            for race_dir in season_dir.iterdir():
                if race_dir.is_dir() and race_dir.name.isdigit():
                    races_raw.append(int(race_dir.name))
            raw_seasons[season] = set(races_raw)
    
    missing = []
    for r in races:
        season = int(r.get('season_id', 0))
        round_num = int(r.get('round', 0))
        if 2002 <= season <= 2026:
            if season not in raw_seasons or round_num not in raw_seasons[season]:
                missing.append((season, round_num))
    
    return sorted(missing)

def main():
    print("=" * 60)
    print("PHASE 22.7 - JOLPICA LAP ACQUISITION (2002-2026)")
    print("=" * 60)
    
    # Load missing races
    missing = load_missing_races()
    print(f"Missing races to acquire: {len(missing)}")
    
    # Show breakdown by season
    by_season = {}
    for s, r in missing:
        by_season.setdefault(s, []).append(r)
    for s in sorted(by_season.keys()):
        print(f"  {s}: {len(by_season[s])} races (rounds {by_season[s]})")
    
    checkpoint = CheckpointStore(CHECKPOINT_FILE)
    results: list[AcquisitionResult] = []
    
    # Load existing manifest if exists
    existing_results = []
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, 'r') as f:
            manifest = json.load(f)
            existing_results = manifest.get("results", [])
            print(f"Loaded {len(existing_results)} existing results from manifest")
    
    completed_keys = {f"jlap:{r['season']}:{r['round']}" for r in existing_results if r.get('status') == 'completed'}
    failed_keys = {f"jlap:{r['season']}:{r['round']}" for r in existing_results if r.get('status') == 'failed'}
    quarantined_keys = {f"jlap:{r['season']}:{r['round']}" for r in existing_results if r.get('status') == 'quarantined'}
    
    print(f"Already completed: {len(completed_keys)}, Failed: {len(failed_keys)}, Quarantined: {len(quarantined_keys)}")
    
    # Process missing races
    for i, (season, round_num) in enumerate(missing, 1):
        key = f"jlap:{season}:{round_num}"
        
        if key in completed_keys:
            print(f"[{i}/{len(missing)}] {season} R{round_num} - SKIPPED (already completed)")
            continue
        if key in failed_keys:
            print(f"[{i}/{len(missing)}] {season} R{round_num} - RETRYING (previously failed)")
        if key in quarantined_keys:
            print(f"[{i}/{len(missing)}] {season} R{round_num} - RETRYING (previously quarantined)")
        
        print(f"[{i}/{len(missing)}] Acquiring {season} Round {round_num}...")
        result = fetch_all_laps_for_race(season, round_num, checkpoint)
        results.append(result)
        
        # Progress update
        if result.status == "completed":
            print(f"  OK: {result.total_laps} laps, {result.pages} pages, {result.bytes_downloaded} bytes")
        elif result.status == "failed":
            print(f"  FAILED: {result.error}")
        elif result.status == "quarantined":
            print(f"  QUARANTINED: {result.error}")
        elif result.status == "skipped":
            print(f"  SKIPPED")
        
        # Save manifest periodically
        if i % 10 == 0:
            all_results = existing_results + [asdict(r) for r in results]
            manifest = {
                "pipeline": "phase22_7_laps_acquisition",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "rate_seconds": RATE_SECONDS,
                "page_size": PAGE_SIZE,
                "total_target_races": len(missing),
                "results": all_results,
                "stats": {
                    "completed": sum(1 for r in all_results if r.get('status') == 'completed'),
                    "failed": sum(1 for r in all_results if r.get('status') == 'failed'),
                    "quarantined": sum(1 for r in all_results if r.get('status') == 'quarantined'),
                    "skipped": sum(1 for r in all_results if r.get('status') == 'skipped'),
                    "total_laps": sum(r.get('total_laps', 0) for r in all_results if r.get('status') == 'completed'),
                    "total_bytes": sum(r.get('bytes_downloaded', 0) for r in all_results),
                }
            }
            MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MANIFEST_FILE, 'w') as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
            print(f"  [Manifest saved: {len(all_results)} results]")
    
    # Final manifest
    all_results = existing_results + [asdict(r) for r in results]
    manifest = {
        "pipeline": "phase22_7_laps_acquisition",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rate_seconds": RATE_SECONDS,
        "page_size": PAGE_SIZE,
        "total_target_races": len(missing),
        "results": all_results,
        "stats": {
            "completed": sum(1 for r in all_results if r.get('status') == 'completed'),
            "failed": sum(1 for r in all_results if r.get('status') == 'failed'),
            "quarantined": sum(1 for r in all_results if r.get('status') == 'quarantined'),
            "skipped": sum(1 for r in all_results if r.get('status') == 'skipped'),
            "total_laps": sum(r.get('total_laps', 0) for r in all_results if r.get('status') == 'completed'),
            "total_bytes": sum(r.get('bytes_downloaded', 0) for r in all_results),
        }
    }
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    # Summary
    print("\n" + "=" * 60)
    print("ACQUISITION SUMMARY")
    print("=" * 60)
    stats = manifest["stats"]
    print(f"Completed: {stats['completed']}")
    print(f"Failed: {stats['failed']}")
    print(f"Quarantined: {stats['quarantined']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Total laps acquired: {stats['total_laps']}")
    print(f"Total bytes: {stats['total_bytes']}")
    print(f"Manifest: {MANIFEST_FILE}")

if __name__ == "__main__":
    main()