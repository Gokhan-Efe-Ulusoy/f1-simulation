"""Phase 22.7 Jolpica capability probe (read-only, rate-safe).

Probes one race (round 1) per representative season to determine endpoint
availability WITHOUT bulk download. Conservative spacing (default 4s),
single small page per season, retries with backoff on 429/5xx.

Usage (from backend/):
    python scripts/phase22_7_probe.py
    python scripts/phase22_7_probe.py --out data/manifests/phase22_7_probe.json

Never writes raw canonical data; only a probe-result JSON manifest.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.provenance import utc_now_iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "data", "manifests", "phase22_7_probe.json")

JOLPICA = "https://api.jolpi.ca/ergast/f1"
PROBE_SEASONS = [2002, 2005, 2010, 2015, 2020, 2023, 2024, 2025, 2026]


def probe_once(season: int, timeout: float = 40.0) -> dict:
    """Single small probe request for season round 1."""
    url = f"{JOLPICA}/{season}/1/laps.json?limit=5&offset=0"
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/22.7-probe"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        return {"season": season, "round": 1, "url": url, "http_status": exc.code,
                "verdict": "RETRY_PENDING" if exc.code in (429, 500, 502, 503, 504) else f"HTTP_{exc.code}",
                "total": None, "n_laps": None, "schema": None}
    except Exception as exc:  # noqa: BLE001 - network/timeout, honestly recorded
        return {"season": season, "round": 1, "url": url, "http_status": None,
                "verdict": "RETRY_PENDING", "error": str(exc)[:200],
                "total": None, "n_laps": None, "schema": None}
    try:
        payload = json.loads(raw.decode("utf-8"))
        mr = payload.get("MRData", {})
        total = mr.get("total")
        races = mr.get("RaceTable", {}).get("Races", [])
        n_laps = len(races[0].get("Laps", [])) if races else 0
        has_timings = bool(races and races[0].get("Laps") and races[0]["Laps"][0].get("Timings"))
        schema = "MRData.RaceTable.Races[].Laps[].Timings[]" if has_timings else "MRData-empty-or-novel"
        total_i = int(total) if total not in (None, "") else 0
        if not races or total_i == 0:
            verdict = "NOT_AVAILABLE"
        else:
            verdict = "AVAILABLE"
        return {"season": season, "round": 1, "url": url, "http_status": status,
                "verdict": verdict, "total": total_i, "n_laps": n_laps,
                "schema": schema, "bytes": len(raw)}
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        return {"season": season, "round": 1, "url": url, "http_status": status,
                "verdict": "RETRY_PENDING", "error": f"unparseable: {exc}"[:200],
                "total": None, "n_laps": None, "schema": None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 22.7 Jolpica probe")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--rate", type=float, default=4.0)
    ap.add_argument("--seasons", default=",".join(map(str, PROBE_SEASONS)))
    args = ap.parse_args()

    seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
    results = []
    for i, season in enumerate(seasons):
        if i > 0:
            time.sleep(args.rate)
        # retry transient once after longer pause
        res = probe_once(season)
        if res["verdict"] == "RETRY_PENDING":
            time.sleep(max(args.rate * 3, 12.0))
            res2 = probe_once(season)
            res["retry"] = res2
            if res2["verdict"] == "AVAILABLE":
                res = res2
        results.append(res)
        print(json.dumps(res))
    doc = {"pipeline": "phase22_7_probe", "generated_at": utc_now_iso(),
           "rate_seconds": args.rate, "results": results}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as h:
        json.dump(doc, h, indent=2, sort_keys=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
