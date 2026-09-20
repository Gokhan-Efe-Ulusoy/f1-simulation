#!/usr/bin/env python3
"""Phase 22.7 Preflight Audit - Historical Lap Backfill Completion."""

import json
import os
import hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path("C:/Users/gokha/Desktop/f1 simülasyonu/backend")
RAW_LAPS = ROOT / "data" / "raw" / "jolpica" / "laps"
CANON_LAPS = ROOT / "data" / "canonical" / "laps_jolpica"
RACES_FILE = ROOT / "data" / "canonical" / "races.json"
PHASE22_6_MANIFEST = ROOT / "data" / "manifests" / "phase22_6_acquisition_manifest.json"
PHASE22_7_MANIFEST = ROOT / "data" / "manifests" / "phase22_7_acquisition_manifest.json"
CHECKPOINT_22_6 = ROOT / "data" / "manifests" / "checkpoint_phase22_6.json"
CHECKPOINT_22_7 = ROOT / "data" / "manifests" / "checkpoint_phase22_7.json"
PROBE_22_7 = ROOT / "data" / "manifests" / "phase22_7_probe.json"

def load_json(path):
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return None

def get_raw_seasons():
    """Get seasons that have raw lap data."""
    if not RAW_LAPS.exists():
        return {}
    seasons = {}
    for season_dir in sorted(RAW_LAPS.iterdir()):
        if season_dir.is_dir() and season_dir.name.isdigit():
            season = int(season_dir.name)
            races = []
            for race_dir in sorted(season_dir.iterdir()):
                if race_dir.is_dir() and race_dir.name.isdigit():
                    round_num = int(race_dir.name)
                    lap_files = list(race_dir.glob("laps-offset*.json"))
                    races.append({
                        "round": round_num,
                        "lap_files": len(lap_files),
                        "has_provenance": all(f.with_suffix(f.suffix + ".provenance.json").exists() for f in lap_files),
                        "has_sha256": all(f.with_suffix(f.suffix + ".sha256").exists() for f in lap_files),
                    })
            seasons[season] = races
    return seasons

def get_canon_seasons():
    """Get seasons that have canonical lap data."""
    if not CANON_LAPS.exists():
        return {}
    seasons = {}
    for season_dir in sorted(CANON_LAPS.iterdir()):
        if season_dir.is_dir() and season_dir.name.startswith("season="):
            season = int(season_dir.name.split("=")[1])
            races = []
            for race_dir in sorted(season_dir.iterdir()):
                if race_dir.is_dir() and race_dir.name.startswith("round="):
                    round_num = int(race_dir.name.split("=")[1])
                    parquet_files = list(race_dir.glob("*.parquet"))
                    races.append({
                        "round": round_num,
                        "parquet_files": len(parquet_files),
                    })
            seasons[season] = races
    return seasons

def get_races_backbone():
    """Get all races from canonical backbone."""
    if not RACES_FILE.exists():
        return {}
    with open(RACES_FILE, 'r') as f:
        races = json.load(f)
    seasons = defaultdict(list)
    for r in races:
        s = r.get('season_id')
        rnd = r.get('round')
        if s and rnd:
            seasons[int(s)].append(int(rnd))
    return {s: sorted(rounds) for s, rounds in seasons.items()}

def check_existing_2002_plus():
    """Check what 2002+ data exists from other sources."""
    # Check external_staging
    ext_staging = ROOT / "data" / "external_staging"
    result = {}
    if ext_staging.exists():
        for f in ext_staging.glob("laps_*.json"):
            result[f.name] = f.stat().st_size
    return result

def main():
    print("=" * 60)
    print("PHASE 22.7 PREFLIGHT AUDIT")
    print("=" * 60)
    
    # Load existing data
    races_backbone = get_races_backbone()
    raw_seasons = get_raw_seasons()
    canon_seasons = get_canon_seasons()
    phase22_6 = load_json(PHASE22_6_MANIFEST)
    phase22_7 = load_json(PHASE22_7_MANIFEST)
    checkpoint_22_6 = load_json(CHECKPOINT_22_6)
    checkpoint_22_7 = load_json(CHECKPOINT_22_7)
    probe_22_7 = load_json(PROBE_22_7)
    existing_2002 = check_existing_2002_plus()
    
    # Target: 2002-2026
    target_seasons = range(2002, 2027)
    
    print("\n1. SEASON COVERAGE (Target: 2002-2026)")
    print("-" * 60)
    
    audit = {
        "season_coverage": {},
        "race_coverage": {},
        "raw_coverage": {},
        "canonical_coverage": {},
        "missing_races": [],
        "verified_races": [],
        "duplicate_risks": [],
        "endpoint_availability": {},
        "estimated_requests": 0,
        "estimated_storage_mb": 0,
        "expected_completion_target": "All available 2002-2026 Jolpica races",
    }
    
    total_target_races = 0
    total_raw_races = 0
    total_canon_races = 0
    missing_races = []
    verified_races = []
    
    for season in target_seasons:
        backbone_races = races_backbone.get(season, [])
        raw_races = raw_seasons.get(season, [])
        canon_races = canon_seasons.get(season, [])
        
        raw_rounds = {r["round"] for r in raw_races}
        canon_rounds = {r["round"] for r in canon_races}
        
        total_target_races += len(backbone_races)
        total_raw_races += len(raw_rounds)
        total_canon_races += len(canon_rounds)
        
        # Determine coverage
        has_raw = len(raw_rounds) > 0
        has_canon = len(canon_rounds) > 0
        
        if has_canon:
            coverage_status = "FULL" if len(canon_rounds) == len(backbone_races) else "PARTIAL"
        elif has_raw:
            coverage_status = "RAW_ONLY"
        else:
            coverage_status = "MISSING"
        
        missing_this_season = [r for r in backbone_races if r not in raw_rounds]
        if missing_this_season:
            missing_races.extend([(season, r) for r in missing_this_season])
        
        verified_this_season = [r for r in backbone_races if r in canon_rounds]
        if verified_this_season:
            verified_races.extend([(season, r) for r in verified_this_season])
        
        audit["season_coverage"][season] = {
            "backbone_races": len(backbone_races),
            "raw_races": len(raw_rounds),
            "canon_races": len(canon_rounds),
            "status": coverage_status,
        }
        audit["race_coverage"][season] = {
            "backbone": backbone_races,
            "raw": sorted(list(raw_rounds)),
            "canon": sorted(list(canon_rounds)),
            "missing": missing_this_season,
        }
        audit["raw_coverage"][season] = len(raw_rounds)
        audit["canonical_coverage"][season] = len(canon_rounds)
        
        print(f"  {season}: Backbone={len(backbone_races)}, Raw={len(raw_rounds)}, Canon={len(canon_rounds)} -> {coverage_status}")
        if missing_this_season:
            print(f"    Missing rounds: {missing_this_season}")
    
    audit["missing_races"] = [{"season": s, "round": r} for s, r in missing_races]
    audit["verified_races"] = [{"season": s, "round": r} for s, r in verified_races]
    
    print(f"\n  TOTAL Target races (2002-2026): {total_target_races}")
    print(f"  TOTAL Raw races acquired: {total_raw_races}")
    print(f"  TOTAL Canonical races: {total_canon_races}")
    print(f"  TOTAL Missing races: {len(missing_races)}")
    
    # Endpoint availability from probe
    print("\n2. ENDPOINT AVAILABILITY (from Phase 22.7 probe)")
    print("-" * 60)
    if probe_22_7 and "results" in probe_22_7:
        for r in probe_22_7["results"]:
            audit["endpoint_availability"][r["season"]] = {
                "verdict": r["verdict"],
                "total_laps": r.get("total", 0),
                "schema": r.get("schema", ""),
            }
            print(f"  {r['season']}: {r['verdict']} ({r.get('total', 0)} laps)")
    
    # Estimate requests
    # Each race may need multiple requests (pagination)
    # Average ~10 pages per race based on existing data
    missing_count = len(missing_races)
    audit["estimated_requests"] = missing_count * 10  # ~10 pages per race
    audit["estimated_storage_mb"] = missing_count * 5  # ~5MB per race
    
    print(f"\n3. ESTIMATED WORK REMAINING")
    print("-" * 60)
    print(f"  Missing races: {missing_count}")
    print(f"  Estimated API requests: {audit['estimated_requests']}")
    print(f"  Estimated storage: {audit['estimated_storage_mb']} MB")
    
    # Checkpoint analysis
    print("\n4. CHECKPOINT STATUS")
    print("-" * 60)
    if checkpoint_22_7:
        completed = checkpoint_22_7.get("completed", [])
        failed = checkpoint_22_7.get("failed", {})
        print(f"  Phase 22.7 completed: {len(completed)}")
        print(f"  Phase 22.7 failed: {len(failed)}")
        # Parse completed for lap tasks
        lap_tasks = [c for c in completed if c.startswith("jlap:")]
        print(f"  Lap tasks completed: {len(lap_tasks)}")
    
    # Duplicate risks
    print("\n5. DUPLICATE RISKS")
    print("-" * 60)
    # Check for races that exist in both raw and canonical
    for season in target_seasons:
        raw_rounds = {r["round"] for r in raw_seasons.get(season, [])}
        canon_rounds = {r["round"] for r in canon_seasons.get(season, [])}
        overlap = raw_rounds & canon_rounds
        if overlap:
            audit["duplicate_risks"].append({
                "season": season,
                "rounds": sorted(list(overlap)),
                "risk": "RAW_CANON_OVERLAP"
            })
    
    # Existing 2002+ from other sources
    print("\n6. EXISTING 2002+ DATA FROM OTHER SOURCES")
    print("-" * 60)
    for fname, size in existing_2002.items():
        print(f"  {fname}: {size} bytes")
        audit.setdefault("other_sources", {})[fname] = size
    
    # Write audit report
    output_path = ROOT / "docs" / "phase22_7_preflight_audit.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write("# Phase 22.7 Preflight Audit\n\n")
        f.write(f"Generated: {json.dumps({'timestamp': 'auto'}, default=str)}\n\n")
        
        f.write("## Season Coverage (2002-2026)\n\n")
        f.write("| Season | Backbone Races | Raw Races | Canonical Races | Status |\n")
        f.write("|--------|----------------|-----------|-----------------|--------|\n")
        for season in target_seasons:
            sc = audit["season_coverage"][season]
            f.write(f"| {season} | {sc['backbone_races']} | {sc['raw_races']} | {sc['canon_races']} | {sc['status']} |\n")
        
        f.write(f"\n**Total Target Races:** {total_target_races}\n")
        f.write(f"**Total Raw Races Acquired:** {total_raw_races}\n")
        f.write(f"**Total Canonical Races:** {total_canon_races}\n")
        f.write(f"**Total Missing Races:** {len(missing_races)}\n")
        
        f.write("\n## Race Coverage Detail\n\n")
        for season in target_seasons:
            rc = audit["race_coverage"][season]
            if rc["missing"]:
                f.write(f"### {season}: Missing {len(rc['missing'])} races\n")
                f.write(f"- Backbone: {rc['backbone']}\n")
                f.write(f"- Raw: {rc['raw']}\n")
                f.write(f"- Canonical: {rc['canon']}\n")
                f.write(f"- **Missing: {rc['missing']}**\n\n")
        
        f.write("## Endpoint Availability (Probe Results)\n\n")
        f.write("| Season | Verdict | Total Laps | Schema |\n")
        f.write("|--------|---------|------------|--------|\n")
        for season, info in audit["endpoint_availability"].items():
            f.write(f"| {season} | {info['verdict']} | {info['total_laps']} | {info['schema']} |\n")
        
        f.write("\n## Estimated Work Remaining\n\n")
        f.write(f"- Missing races: {missing_count}\n")
        f.write(f"- Estimated API requests: {audit['estimated_requests']}\n")
        f.write(f"- Estimated storage: {audit['estimated_storage_mb']} MB\n")
        
        f.write("\n## Duplicate Risks\n\n")
        if audit["duplicate_risks"]:
            f.write("| Season | Rounds | Risk |\n")
            f.write("|--------|--------|------|\n")
            for dr in audit["duplicate_risks"]:
                f.write(f"| {dr['season']} | {dr['rounds']} | {dr['risk']} |\n")
        else:
            f.write("No duplicate risks detected.\n")
        
        f.write("\n## Other Sources with 2002+ Data\n\n")
        for fname, size in existing_2002.items():
            f.write(f"- {fname}: {size} bytes\n")
        
        f.write("\n## Completion Target\n\n")
        f.write(f"{audit['expected_completion_target']}\n")
    
    print(f"\n[OK] Preflight audit written to: {output_path}")
    return audit

if __name__ == "__main__":
    main()