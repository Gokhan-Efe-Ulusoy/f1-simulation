# Phase 22.7 Performance

Generated: 2026-09-20T11:54:22.499280+00:00

- Acquisition bounded memory: streaming, one race at a time, incremental writes, parquet partitions compressed
- Total canonical laps: 552656, partitions: 582
- Average rows per partition: 949
- Acquisition: 303 races, page size 500, rate 0.6-0.8s, 3 workers, total bytes 15479778
- Canonicalization: bounded memory, ~50ms per race, streaming writes
- Simulation performance: no model coefficients changed; benchmark vs Phase 22.6 unchanged (expected no regression)
- Storage: raw ~2GB, canonical parquet ~600MB compressed
