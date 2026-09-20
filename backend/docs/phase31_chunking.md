# Phase 31 — Deterministic Chunking

## Model

- `seed_i = base_seed + index*1000 + stream_offset` (pace 0, qual +2, rel +3, weather +500, RC +600+lap*7919, AR1 +100 shared sliced, strategy +700).
- Worker/chunk/priority/timestamp/UUID/process/thread/execution_order MUST NOT enter derivation.
- AR1 Level B shared `default_rng(seed+100+lap).normal((N,D))` sliced via discard `start*D` draws (`rng.ar1_chunk_noise`), verified exact slice.

## Equivalence

- `run(N, chunk=500)` == `run(N, chunk=1000)` == `run(N, chunk=5000)` == unchunked: identical per-sim positions, integer counts, win/podium probs, result hash.
- Tested chunk 1/10/100/500/1000 for N=10/20/100. Chunk manifest `{base_seed,total,chunk_size,chunks[{index,start,end,status,result_hash}],aggregate_hash,deterministic:true}` excludes timestamps.
- Memory `O(chunk*D + chunk*L)`, never `(N,D,L,features)`. Public API cap N≤5000 preserved; internal supports to 100k via 100×1000.
- Aggregation: exact integer counts, canonical ordering by `simulation_index`, stable reduction; floats documented where unavoidable (none for counts).
