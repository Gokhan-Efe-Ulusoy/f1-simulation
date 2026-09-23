#!/usr/bin/env python3
"""Verify the F1 dataset against committed manifests (Phase 33).

Read-only validation. This script NEVER downloads, repairs, regenerates,
or otherwise mutates data. Missing layers are reported as NOT_AVAILABLE
(exit 0); corruption (hash mismatch, duplicate PKs, orphan references,
manifest inconsistency) exits non-zero.

Usage:
    python scripts/verify_dataset.py           # full local verification
    python scripts/verify_dataset.py --offline # manifests only (CI-safe)

Exit codes:
    0 — OK (all present layers verified; absent layers listed as NOT_AVAILABLE)
    2 — CORRUPTION or manifest inconsistency detected
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Resolve backend root regardless of cwd (script lives in backend/scripts/).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = BACKEND_ROOT / "data"
MANIFESTS = DATA_ROOT / "manifests"

EXPECTED_DATASET = "f1-dataset-v1.3"


def sha8(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true",
                    help="validate committed manifests only; skip on-disk data checks")
    args = ap.parse_args()

    errors: list[str] = []
    notes: list[str] = []
    checked = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal checked
        checked += 1
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            errors.append(name)

    # --- 1. Core manifests exist ------------------------------------------------
    v13_path = MANIFESTS / "f1-dataset-v1.3.json"
    check("manifest f1-dataset-v1.3.json exists", v13_path.exists())
    if not v13_path.exists():
        print("NOT_AVAILABLE: dataset manifest missing; cannot verify anything further.")
        return 2
    v13 = load_json(v13_path)
    check("dataset_id == " + EXPECTED_DATASET, v13.get("dataset_id") == EXPECTED_DATASET,
          str(v13.get("dataset_id")))
    check("version == " + EXPECTED_DATASET, v13.get("version") == EXPECTED_DATASET,
          str(v13.get("version")))
    check("dataset frozen", v13.get("frozen") is True and v13.get("dataset_frozen") is True)
    check("calibration_changed is False", v13.get("calibration_changed") is False)
    check("simulation_behavior_changed is False",
          v13.get("simulation_behavior_changed") is False)

    counts = v13.get("record_counts", {})
    for key in ("races", "results", "laps_jolpica", "pitstops_jolpica"):
        check(f"record_counts.{key} present", key in counts, str(counts.get(key)))

    hashes = v13.get("hashes", {})
    for key in ("races", "results", "laps_jolpica"):
        check(f"hashes.{key} present", key in hashes, str(hashes.get(key)))

    # --- 2. Registry consistency ------------------------------------------------
    reg_path = MANIFESTS / "registry.json"
    check("registry.json exists", reg_path.exists())
    if reg_path.exists():
        registry = load_json(reg_path)
        entry = next((e for e in registry if e.get("dataset_id") == EXPECTED_DATASET), None)
        check("registry contains " + EXPECTED_DATASET, entry is not None)
        if entry is not None:
            check("registry hashes match manifest",
                  entry.get("hashes") == hashes,
                  f"registry={entry.get('hashes')} manifest={hashes}")
            check("registry parent is f1-dataset-v1.2",
                  entry.get("parent_dataset") == "f1-dataset-v1.2",
                  str(entry.get("parent_dataset")))

    for name in ("dataset-manifest.json", "dataset-manifest-v1.3.json"):
        check(f"manifest {name} exists", (MANIFESTS / name).exists())

    # --- 3. Tracked lightweight layers ------------------------------------------
    for name in ("derived/constructor_features.json",
                 "derived/decomposition.json",
                 "derived/scenarios_sample.json",
                 "validation/coverage_report.json",
                 "regulations/regulation_evidence.json",
                 "licensing.json"):
        check(f"tracked layer {name} exists", (DATA_ROOT / name).exists())

    calib_models = sorted((DATA_ROOT / "calibration" / "models").glob("*.json")) \
        if (DATA_ROOT / "calibration" / "models").exists() else []
    check("calibration models present", len(calib_models) > 0, f"{len(calib_models)} files")

    if args.offline:
        print(f"\nOffline manifest validation: {checked} checks, "
              f"{len(errors)} failures. On-disk data layers skipped (--offline).")
        return 2 if errors else 0

    # --- 4. Canonical data (optional layer) -------------------------------------
    canon = DATA_ROOT / "canonical"
    races_p = canon / "races.json"
    results_p = canon / "results.json"
    if not races_p.exists() or not results_p.exists():
        notes.append("NOT_AVAILABLE: data/canonical/races.json + results.json "
                     "(raw/canonical layers are intentionally not committed; "
                     "see docs/data_reproducibility.md for reconstruction).")
    else:
        races = load_json(races_p)
        results = load_json(results_p)
        check("canonical races.json is a list", isinstance(races, list), f"n={len(races) if isinstance(races, list) else '?'}")
        check("canonical results.json is a list", isinstance(results, list), f"n={len(results) if isinstance(results, list) else '?'}")
        if isinstance(races, list):
            check("races row count matches manifest",
                  len(races) == counts.get("races"), f"{len(races)} vs {counts.get('races')}")
            check("races sha8 matches manifest",
                  sha8(races_p) == hashes.get("races"),
                  f"{sha8(races_p)} vs {hashes.get('races')}")
            race_ids = [r.get("race_id") for r in races]
            check("races race_id unique (no duplicate PKs)",
                  len(set(race_ids)) == len(race_ids))
        if isinstance(results, list):
            check("results row count matches manifest",
                  len(results) == counts.get("results"),
                  f"{len(results)} vs {counts.get('results')}")
            check("results sha8 matches manifest",
                  sha8(results_p) == hashes.get("results"),
                  f"{sha8(results_p)} vs {hashes.get('results')}")
            if isinstance(races, list):
                race_id_set = {r.get("race_id") for r in races}
                orphans = [x for x in results if x.get("race_id") not in race_id_set]
                check("results.race_id has no orphans", len(orphans) == 0,
                      f"{len(orphans)} orphans" if orphans else "0 orphans")

    # --- Report -----------------------------------------------------------------
    print()
    for n in notes:
        print(n)
    print(f"\nDataset verification: {checked} checks, {len(errors)} failures.")
    if errors:
        print("CORRUPTION/INCONSISTENCY in: " + ", ".join(errors))
        return 2
    print("Status: OK" + (" (some layers NOT_AVAILABLE, see above)" if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
