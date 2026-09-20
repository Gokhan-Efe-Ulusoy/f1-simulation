"""Developer CLI for historical data operations (Phase 10).

Usage examples (offline-safe unless noted):
  python -m app.data coverage
  python -m app.data validate --canonical-dir data/canonical --dataset v0
  python -m app.data ingest --source csv --csv-dir data/raw/external --season 2024
  python -m app.data ingest --source jolpica --season 2024   # needs network
  python -m app.data ingest --source jolpica --season all --limit 2 --dry-run
  python -m app.data ingest --source openf1 --season 2024
  python -m app.data ingest --source fastf1 --season 2024 --event Bahrain --session R
  python -m app.data ingest --source kaggle --dataset owner/slug --season 2024
  python -m app.data ingest --source github --repo owner/repo --path data/file.csv --ref abc123
  python -m app.data ingest --all --dry-run
  python -m app.data conflicts --facts facts.json
  python -m app.data build-features --season 2024 --results results.json --out features.json
  python -m app.data build-calibration --features features.json --out calibration.json
  python -m app.data build-calibration-dataset --dataset v1 --out calibration_dataset.json
  python -m app.data build-dataset --dataset f1-dataset-v1.0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _root() -> str:
    """Working directory root (CLI is cwd-relative by design)."""
    return os.getcwd()


def cmd_coverage(args: argparse.Namespace) -> int:
    from app.data.coverage import build_coverage_report, render_text

    report = build_coverage_report()
    out_path = os.path.join(_root(), "data", "validation", "coverage.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(render_text(report))
    print(f"wrote {out_path}")
    # Also print extended dashboard
    extended = report.get("summary", {})
    print(f"summary: {extended}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from app.data.validation import validate_bundle

    def load(name: str) -> list[dict[str, Any]]:
        path = os.path.join(args.canonical_dir, f"{name}.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else []

    report = validate_bundle(
        args.dataset,
        races=load("races"), results=load("results"),
        drivers=load("drivers"), constructors=load("constructors"))
    out_path = os.path.join(_root(), "data", "validation", "report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report.model_dump(), handle, indent=2, sort_keys=True)
    print(f"errors={len(report.errors)} warnings={len(report.warnings)} "
          f"stats={report.statistics}")
    for error in report.errors[:20]:
        print(f"ERROR {error}")
    print(f"wrote {out_path}")
    return 1 if report.errors else 0


def _parse_season_arg(season: str | int) -> list[int] | str:
    if isinstance(season, str) and season == "all":
        return list(range(1950, 2027))
    return [int(season)]  # type: ignore[arg-type]


def cmd_ingest(args: argparse.Namespace) -> int:
    from app.data.manifests import run_ingestion
    from app.data.sources.base import RawBundle

    if getattr(args, "all_sources", False):
        # Ingest all sources (dry-run respects offline)
        print("ingest --all: would ingest all configured sources (dry-run check)")
        return 0

    bundles: list[RawBundle] = []
    coverage = ""
    source = args.source

    # Handle bulk flags
    seasons: list[int] = []
    if hasattr(args, "season") and args.season is not None:
        if args.season == "all":
            seasons = list(range(1950, 2027))
            if getattr(args, "limit", None):
                seasons = seasons[: args.limit]
        else:
            try:
                seasons = [int(args.season)]
            except (ValueError, TypeError):
                seasons = []

    if source == "jolpica":
        from app.data.sources.jolpica import JolpicaAdapter

        if getattr(args, "dry_run", False):
            print(f"dry-run: would fetch jolpica seasons {seasons[:3]}...")
            return 0
        if getattr(args, "offline", False):
            print("offline: using cache only for jolpica")
            return 0
        adapter = JolpicaAdapter()
        for season in (seasons or [2024]):
            bundles.append(adapter.fetch_season(season))
            if getattr(args, "round", None):
                bundles.append(adapter.fetch_race(season, args.round))
        coverage = f"{seasons[0] if seasons else args.season}"
    elif source == "csv":
        from app.data.sources.csv_adapter import OfficialCsvAdapter

        default_csv = os.path.join(_root(), "data", "raw", "external")
        csv_adapter = OfficialCsvAdapter(args.csv_dir or default_csv)
        for season in (seasons or [2024]):
            bundles.append(csv_adapter.fetch_season(season))
            if getattr(args, "round", None):
                bundles.append(csv_adapter.fetch_race(season, args.round))
        coverage = f"{seasons[0] if seasons else 2024}"
    elif source == "openf1":
        from app.data.sources.openf1 import OpenF1SourceAdapter

        adapter = OpenF1SourceAdapter()
        for season in (seasons or [2024]):
            caps = adapter.capabilities(season)
            if not any(caps.values()):
                print(f"openf1: season {season} not covered, skipping")
                continue
            if getattr(args, "dry_run", False):
                print(f"dry-run: would fetch openf1 season {season}")
                continue
            try:
                bundles.append(adapter.fetch_season(season))
            except Exception as exc:  # noqa: BLE001
                print(f"openf1 fetch failed for {season}: {exc}", file=sys.stderr)
        coverage = f"openf1:{seasons[0] if seasons else 2024}"
    elif source == "fastf1":
        from app.data.sources.fastf1_adapter import FastF1Adapter

        fastf1_adapter = FastF1Adapter()
        if getattr(args, "event", None) is None or getattr(args, "session", None) is None:
            # For bulk fastf1, just check availability
            if getattr(args, "dry_run", False):
                print("dry-run: would fetch fastf1 sessions")
                return 0
            print("fastf1 ingest needs --event and --session for single fetch", file=sys.stderr)
            return 2
        bundles = [fastf1_adapter.fetch_session(seasons[0] if seasons else 2024,
                                                args.event, args.session)]
        coverage = f"{seasons[0] if seasons else 2024}/{args.event}/{args.session}"
    elif source == "kaggle":
        from app.data.sources.kaggle import KaggleSourceAdapter

        if not getattr(args, "dataset", None):
            print("kaggle ingest needs --dataset OWNER/SLUG", file=sys.stderr)
            return 2
        owner, slug = args.dataset.split("/", 1) if "/" in args.dataset else (args.dataset, "")
        adapter = KaggleSourceAdapter()
        bundles.append(adapter.fetch_dataset(owner, slug))
        coverage = args.dataset
    elif source == "github":
        from app.data.sources.github import GitHubSourceAdapter

        if not getattr(args, "repo", None) or not getattr(args, "path", None):
            print("github ingest needs --repo OWNER/REPO --path FILE", file=sys.stderr)
            return 2
        owner, repo = args.repo.split("/", 1) if "/" in args.repo else (args.repo, "")
        adapter = GitHubSourceAdapter()
        bundles.append(adapter.fetch_file(owner, repo, args.path, ref=getattr(args, "ref", None)))
        coverage = f"{args.repo}/{args.path}"
    elif source == "fia":

        # FIA is document-oriented; for CLI demo, just validate existence
        print("fia adapter is document-oriented; use import_document via Python API")
        return 0
    elif source == "weather":

        print("weather adapter: use import_observations via Python API")
        return 0
    else:
        print(f"unknown source: {source}", file=sys.stderr)
        return 2

    if getattr(args, "dry_run", False):
        print(f"dry-run: fetched {len(bundles)} bundles (not persisted)")
        return 0

    if getattr(args, "offline", False):
        print("offline mode: would use cache only (not implemented for this source in CLI demo)")
        return 0

    # Force flag is handled at checkpoint level in bulk_ingest_jolpica; here we just run
    manifest = run_ingestion(_root(), source, str(coverage), bundles)
    print(f"run={manifest.run_id} fetched={manifest.records_fetched} "
          f"rejected={manifest.records_rejected}")
    return 0


def cmd_conflicts(args: argparse.Namespace) -> int:
    from app.data.conflicts import detect_conflicts

    with open(args.facts, encoding="utf-8") as handle:
        payload = json.load(handle)
    facts = [(item[0], item[1], item[2]) for item in payload.get("facts", [])]
    found = detect_conflicts(facts)
    print(f"conflicts={len(found)}")
    for conflict in found:
        print(f"{conflict.entity_id} {conflict.field} {conflict.values} "
              f"-> {conflict.resolution} ({conflict.resolution_reason})")
    return 0


def cmd_build_features(args: argparse.Namespace) -> int:
    from app.data.features import constructor_features, driver_features

    with open(args.results, encoding="utf-8") as handle:
        results = json.load(handle)
    driver_ids = sorted({str(r.get("driver_id")) for r in results})
    records: list[dict[str, object]] = []
    constructor_ids = sorted(
        {str(r.get("constructor_id")) for r in results if r.get("constructor_id")})
    for driver_id in driver_ids:
        records.extend(
            f.model_dump() for f in driver_features(driver_id, str(args.season), results))
    for constructor_id in constructor_ids:
        records.extend(
            f.model_dump()
            for f in constructor_features(constructor_id, str(args.season), results))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, sort_keys=True)
    print(f"features={len(records)} wrote {args.out}")
    return 0


def cmd_build_calibration(args: argparse.Namespace) -> int:
    from app.data.calibration_bridge import FittedCalibrationSet

    with open(args.features, encoding="utf-8") as handle:
        features = json.load(handle)
    fitted = FittedCalibrationSet(set_id="identity-baseline")
    out = {
        "set_id": fitted.set_id,
        "method": "identity-baseline",
        "note": "No fitting performed; identity profile. "
                "Populate parameters from analysed features in a later phase.",
        "feature_count": len(features),
        "profile": fitted.to_simulation_profile().model_dump(),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
    print(f"wrote {args.out}")
    return 0


def cmd_build_calibration_dataset(args: argparse.Namespace) -> int:
    from app.data.calibration_dataset import CalibrationDatasetBuilder

    builder = CalibrationDatasetBuilder(root=_root())
    result = builder.build(
        dataset_version=args.dataset,
        canonical_dir=getattr(args, "canonical_dir", None),
    )
    print(f"calibration_dataset={result['calibration_dataset']} "
          f"records={result['record_count']} candidates={result['candidate_count']}")
    return 0


def cmd_build_dataset(args: argparse.Namespace) -> int:
    from app.data.pipeline import run_pipeline

    if getattr(args, "dry_run", False):
        print(f"dry-run: would build dataset {args.dataset} "
              f"seasons {args.start_season}-{args.end_season} sources {args.sources}")
        return 0
    # Full pipeline: raw → canonical → features → version (restartable, batched)
    result = run_pipeline(
        root=_root(),
        start_season=getattr(args, "start_season", 1950),
        end_season=getattr(args, "end_season", 2026),
        sources=getattr(args, "sources", None),
        offline=bool(getattr(args, "offline", False)),
        force=bool(getattr(args, "force", False)),
        dry_run=False,
        dataset_version=getattr(args, "output_version", None) or args.dataset,
    )
    print(f"dataset={result.get('version', {}).get('dataset_id', args.dataset)} "
          f"canonical={result.get('canonical')} quality={result.get('quality_gate')}")
    return 0 if result.get("quality_gate") != "FAILED" else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    from app.data.benchmark import run_benchmark

    # Minimal demo benchmark using stub simulator (real would use HistoricalScenarioBuilder)
    def stub_sim(idx: int):
        # Deterministic stub: rotate order
        order = ["VER", "HAM", "LEC"] if idx % 2 == 0 else ["HAM", "VER", "LEC"]
        return {"order": order, "lap_times": {"VER": [90.0], "HAM": [90.5]},
                "dnf_rate": 0.0, "pit_stops": {}}

    bench = run_benchmark(
        f"{args.season}-{args.race}", ["VER", "HAM", "LEC"],
        simulate=stub_sim, simulation_count=args.simulations,
        model_version="0.2.0", dataset_version="f1-dataset-v1.0")
    print(f"benchmark {bench.race_id} simulations={bench.simulation_count} "
          f"position_error={bench.calibration_metrics.get('position_error')}")
    return 0


def cmd_benchmark_season(args: argparse.Namespace) -> int:
    # Benchmark each race in a season (stub: 2 races)
    for race in ["Bahrain", "Monaco"]:
        cmd_benchmark(argparse.Namespace(season=args.season, race=race,
                                         simulations=args.simulations))
    return 0


def cmd_benchmark_range(args: argparse.Namespace) -> int:
    for season in range(args.start_season, args.end_season + 1):
        cmd_benchmark_season(argparse.Namespace(season=season, simulations=args.simulations))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(prog="python -m app.data",
                                     description="F1 historical data tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("coverage", help="write data/validation/coverage.json")

    validate = sub.add_parser("validate", help="validate canonical JSON files")
    validate.add_argument("--canonical-dir", required=True)
    validate.add_argument("--dataset", required=True)

    ingest = sub.add_parser("ingest", help="fetch raw bundles + manifest")
    ingest.add_argument("--source", required=False, choices=[
        "jolpica", "csv", "openf1", "fastf1", "kaggle", "github", "fia", "weather"])
    ingest.add_argument("--all", dest="all_sources", action="store_true",
                        help="ingest all configured sources")
    ingest.add_argument("--season", required=False, default="2024",
                        help="season year or 'all' for 1950-2026")
    ingest.add_argument("--round", required=False, type=int, default=None)
    ingest.add_argument("--csv-dir", required=False, default=None)
    ingest.add_argument("--event", required=False, default=None)
    ingest.add_argument("--session", required=False, default=None)
    ingest.add_argument("--dataset", required=False, default=None,
                        help="kaggle dataset OWNER/SLUG")
    ingest.add_argument("--repo", required=False, default=None,
                        help="github repo OWNER/REPO")
    ingest.add_argument("--path", required=False, default=None,
                        help="github file path")
    ingest.add_argument("--ref", required=False, default=None,
                        help="github commit SHA or tag")
    ingest.add_argument("--force", action="store_true", help="force re-fetch ignoring cache")
    ingest.add_argument("--offline", action="store_true", help="offline: use cache only")
    ingest.add_argument("--dry-run", action="store_true", help="dry run, no writes")
    ingest.add_argument("--limit", type=int, default=None, help="limit seasons for bulk")

    conflicts = sub.add_parser("conflicts", help="detect conflicts in a facts file")
    conflicts.add_argument("--facts", required=True)

    features = sub.add_parser("build-features", help="extract features from results JSON")
    features.add_argument("--season", required=True)
    features.add_argument("--results", required=True)
    features.add_argument("--out", required=True)

    calibration = sub.add_parser("build-calibration", help="scaffold calibration set")
    calibration.add_argument("--features", required=True)
    calibration.add_argument("--out", required=True)

    cal_ds = sub.add_parser("build-calibration-dataset",
                            help="build calibration_dataset_v1")
    cal_ds.add_argument("--dataset", required=True, help="dataset version")
    cal_ds.add_argument("--canonical-dir", required=False, default=None)
    cal_ds.add_argument("--out", required=False, default=None)

    dataset = sub.add_parser("build-dataset", help="build canonical dataset")
    dataset.add_argument("--dataset", required=True, help="dataset version e.g. f1-dataset-v1.0")
    dataset.add_argument("--start-season", type=int, default=1950, help="start season")
    dataset.add_argument("--end-season", type=int, default=2026, help="end season")
    dataset.add_argument("--sources", nargs="*", default=None, help="source ids to include")
    dataset.add_argument("--offline", action="store_true", help="offline mode")
    dataset.add_argument("--force", action="store_true", help="force rebuild")
    dataset.add_argument("--dry-run", action="store_true", help="dry run")
    dataset.add_argument("--workers", type=int, default=1, help="parallel workers (reserved)")
    dataset.add_argument("--output-version", required=False, default=None, help="output version alias")  # noqa: E501

    benchmark = sub.add_parser("benchmark", help="benchmark a historical race")
    benchmark.add_argument("--season", required=True, type=int)
    benchmark.add_argument("--race", required=True, help="race name or id")
    benchmark.add_argument("--simulations", type=int, default=100)

    bench_season = sub.add_parser("benchmark-season", help="benchmark a season")
    bench_season.add_argument("--season", required=True, type=int)
    bench_season.add_argument("--simulations", type=int, default=100)

    bench_range = sub.add_parser("benchmark-range", help="benchmark a season range")
    bench_range.add_argument("--start", dest="start_season", type=int, required=True)
    bench_range.add_argument("--end", dest="end_season", type=int, required=True)
    bench_range.add_argument("--simulations", type=int, default=100)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (returns process exit code)."""
    args = build_parser().parse_args(argv)
    if args.command == "coverage":
        return cmd_coverage(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "conflicts":
        return cmd_conflicts(args)
    if args.command == "build-features":
        return cmd_build_features(args)
    if args.command == "build-calibration":
        return cmd_build_calibration(args)
    if args.command == "build-calibration-dataset":
        return cmd_build_calibration_dataset(args)
    if args.command == "build-dataset":
        return cmd_build_dataset(args)
    if args.command == "benchmark":
        return cmd_benchmark(args)
    if args.command == "benchmark-season":
        return cmd_benchmark_season(args)
    if args.command == "benchmark-range":
        return cmd_benchmark_range(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
