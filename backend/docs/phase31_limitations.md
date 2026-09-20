# Phase 31 — Limitations

- Scientific: dataset f1-dataset-v1.3, calibration/production models unchanged, fuel NON_IDENTIFIABLE, tyre LIMITED/NON_IDENTIFIABLE, no promotion.
- Chunking exact for tested N≤1000; larger N (50k/100k) architecturally ready (100×1000) but not benchmarked publicly; API cap N≤5000 preserved.
- Distributed: InProcess default; Redis optional, not multi-host tested; priority FIFO within level, no aging.
- Progress stage-level throttled; per-sample not per-lap for race.
- Timeout 300s heuristic; long legit sims need heartbeat tuning.
- Observability lightweight, no full tracing.
