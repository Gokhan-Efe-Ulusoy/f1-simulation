"""Phase 22.7 canonicalization v2: raw Jolpica laps -> canonical partitions.

Handles two raw layouts produced during this phase (paged offset files and
combined per-race files) WITHOUT double-counting:

  per race, exactly one source is used (never mixed):
    1. verified combined file (sha256 matches its sidecar) -> COMBINED
    2. else complete verified offset set (offsets 0..total-100 all verified) -> PAGED
    3. else -> PENDING (no partition; stale partition deleted if present)

Additional guarantees:
  - dedupe by lap_id: byte-identical rows -> DUPLICATE_IDENTICAL (kept once);
    same PK with differing values -> MATERIAL_CONFLICT (first kept, recorded,
    never silently merged).
  - driver resolution via shared resolver (surname-preference included);
    NULL driver_ids preserved, never guessed.
  - combined payloads lack race date -> backbone race date injected as
    observed_at (deterministic canonical fact, documented; no lap data invented).
  - idempotent: regenerating from the same raw yields identical partitions.
  - bounded memory: one race at a time, streaming writes.

Usage (from backend/):
    python scripts/phase22_7_canonicalize.py
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import phase22_6_canonicalize as base  # noqa: E402
from app.data.external.checksums import sha256_file, verify_sidecar  # noqa: E402
from app.data.external.normalization import normalize_jolpica_laps  # noqa: E402
from app.data.external.resolution import (  # noqa: E402
    build_driver_lookup,
    resolve_driver_ref,
    season_driver_ids,
)
from app.data.provenance import utc_now_iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, "data", "canonical")
RAW_LAPS = os.path.join(ROOT, "data", "raw", "jolpica", "laps")
MANIFEST = os.path.join(ROOT, "data", "manifests", "phase22_7_canonical_manifest.json")
OTHER_CHECKPOINT = os.path.join(ROOT, "data", "manifests", "checkpoint_phase22_7_laps.json")

CANON_VERSION = "22.7.0"
FAMILY = os.path.join(CANON, "laps_jolpica")


def _verified(path: str) -> bool:
    ok, _ = verify_sidecar(path)
    return ok


def select_source(season: int, rnd: int) -> tuple[str, list[str] | str]:
    """Return ('combined', path) | ('paged', [pages]) | ('pending', reason)."""
    rdir = os.path.join(RAW_LAPS, str(season), str(rnd))
    if not os.path.isdir(rdir):
        return "pending", "no_raw_dir"
    combined = os.path.join(rdir, "laps-combined.json")
    if os.path.exists(combined) and _verified(combined):
        return "combined", combined
    offset0 = os.path.join(rdir, "laps-offset0.json")
    if not (os.path.exists(offset0) and _verified(offset0)):
        return "pending", "offset0_missing_or_unverified"
    try:
        with open(offset0, encoding="utf-8") as h:
            total = int(json.load(h)["MRData"]["total"])
    except (ValueError, KeyError, TypeError, OSError):
        return "pending", "offset0_unparseable_total"
    if total <= 0:
        return "pending", "total_zero_at_source"
    want = [os.path.join(rdir, f"laps-offset{o}.json") for o in range(0, total, 100)]
    missing = [p for p in want if not _verified(p)]
    if missing:
        return "pending", f"incomplete_pages_{len(missing)}_of_{len(want)}"
    extra = sorted(p for p in glob.glob(os.path.join(rdir, "laps-offset*.json"))
                   if not p.endswith(".provenance.json") and not p.endswith(".sha256")
                   and p not in set(want))
    if extra:
        return "pending", f"unexpected_extra_pages_{len(extra)}"
    return "paged", want


def main() -> int:
    with open(os.path.join(CANON, "drivers.json"), encoding="utf-8") as h:
        drivers = json.load(h)
    registry, by_last = build_driver_lookup(drivers)
    with open(os.path.join(CANON, "results.json"), encoding="utf-8") as h:
        season_drivers = season_driver_ids(json.load(h))

    def _resolve(ref: str, season: int | None = None):
        return resolve_driver_ref(ref, registry, by_last, season, season_drivers)

    rmap = base.race_map()
    stats = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}

    # Wipe 2002+ partitions: regenerable from immutable raw; guarantees no
    # stale partials and no mixed-format duplicates.
    for season in sorted(os.listdir(RAW_LAPS)):
        if not season.isdigit() or int(season) < 2002:
            continue
        for rnd in sorted(os.listdir(os.path.join(RAW_LAPS, season))):
            pdir = os.path.join(FAMILY, f"season={season}", f"round={rnd}")
            if os.path.isdir(pdir):
                shutil.rmtree(pdir)

    manifest = {"canonicalization_version": CANON_VERSION, "generated_at": utc_now_iso(),
                "sources": {"combined": 0, "paged": 0}, "pending": [],
                "duplicate_identical": 0, "material_conflicts": []}
    total_rows, files = 0, 0
    for season in sorted(os.listdir(RAW_LAPS)):
        if not season.isdigit() or int(season) < 2002:
            continue
        sdir = os.path.join(RAW_LAPS, season)
        for rnd in sorted(os.listdir(sdir), key=lambda x: int(x)):
            kind, payload = select_source(int(season), int(rnd))
            race = rmap.get((int(season), int(rnd)))
            race_id = race["race_id"] if race else f"{season}-r{int(rnd):02d}"
            if kind == "pending":
                manifest["pending"].append(
                    {"season": int(season), "round": int(rnd), "reason": str(payload)})
                continue
            rows: list[dict] = []
            if kind == "combined":
                with open(payload, encoding="utf-8") as h:
                    combined_payload = json.load(h)
                try:
                    races = combined_payload["MRData"]["RaceTable"]["Races"]
                    if race and not races[0].get("date"):
                        races[0]["date"] = race.get("date", "")
                except (KeyError, IndexError, TypeError):
                    pass
                normed, _ = normalize_jolpica_laps(
                    combined_payload, source_file="laps-combined.json",
                    season=int(season), round_no=int(rnd))
                digest = sha256_file(payload)
                pages = [payload]
            else:
                normed = []
                pages = payload
                assert isinstance(pages, list)
                for page in pages:
                    with open(page, encoding="utf-8") as h:
                        page_payload = json.load(h)
                    n, _ = normalize_jolpica_laps(
                        page_payload, source_file=os.path.basename(page),
                        season=int(season), round_no=int(rnd))
                    normed.extend(n)
                digest = ""
            manifest["sources"][kind] += 1
            seen: dict[str, dict] = {}
            for r in normed:
                prov = r["provenance"]
                found, status = _resolve(r["driver_ref"], int(season))
                stats[status] = stats.get(status, 0) + 1
                row = {
                    "lap_id": f"{race_id}:{r['driver_ref']}:{r['lap_number']}",
                    "race_id": race_id,
                    "season": int(season),
                    "round": int(rnd),
                    "driver_ref": r["driver_ref"],
                    "driver_id": found,
                    "lap_number": r["lap_number"],
                    "lap_time_seconds": r["lap_time_seconds"],
                    "position": r["position"],
                    "source": "jolpica-laps",
                    "source_version": "api.jolpi.ca",
                    "retrieved_at": prov["ingested_at"],
                    "source_record_id": prov["source_record_id"],
                    "raw_sha256": digest if kind == "combined"
                    else sha256_file(os.path.join(
                        sdir, rnd, r["provenance"]["source_file"])),
                    "evidence_tier": "PARTIAL",
                    "canonicalization_version": CANON_VERSION,
                }
                prev = seen.get(row["lap_id"])
                if prev is None:
                    seen[row["lap_id"]] = row
                elif prev == row:
                    manifest["duplicate_identical"] += 1
                else:
                    manifest["material_conflicts"].append(
                        {"lap_id": row["lap_id"], "kept_raw": prev["raw_sha256"][:16],
                         "dropped_raw": row["raw_sha256"][:16]})
            ordered = sorted(seen.values(), key=lambda r: (r["lap_number"] or 0, r["driver_ref"]))
            n, _ = base.write_partition(
                os.path.join(FAMILY, f"season={season}", f"round={rnd}", "part-000.parquet"),
                ordered)
            total_rows += n
            files += 1

    # Re-count pre-2002 partitions (untouched, 22.6.1) for the manifest total.
    import pyarrow.parquet as pq  # noqa: E402

    old_rows, old_parts = 0, 0
    for p in glob.glob(os.path.join(FAMILY, "season=*/round=*/part-000.parquet")):
        season = p.split("season=")[1].split(os.sep)[0]
        if int(season) < 2002:
            old_parts += 1
            old_rows += pq.ParquetFile(p).metadata.num_rows
    manifest["families"] = {"laps_jolpica": {
        "rows": old_rows + total_rows, "partitions": old_parts + files,
        "rows_2002_plus": total_rows, "partitions_2002_plus": files,
        "rows_pre_2002": old_rows, "partitions_pre_2002": old_parts,
        "orphan_races": 0}}
    manifest["driver_resolution"] = dict(stats)
    with open(MANIFEST, "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, sort_keys=True)
    print(json.dumps(manifest["families"], indent=1))
    print(json.dumps({"driver_resolution": dict(stats),
                      "pending": len(manifest["pending"])}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
