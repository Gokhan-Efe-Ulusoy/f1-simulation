# Phase 31 — Determinism

- Same seed+request+dataset+engine/model → identical canonical result (per-sim positions, counts, win/podium, result hash).
- Different seed → different stochastic result.
- Different chunk size / worker count / execution order → identical (canonical sort by simulation_index).
- Retry same chunk → identical.
- API → direct engine equivalence preserved.
- RNG isolation: strategy 700, AR1 100, RC 600, weather 500, qual +2, rel +3 unchanged; API/queue/store/hashing/metrics never consume RNG.
- Persistence does not alter result (JSON round-trip within tolerance).
