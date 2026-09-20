# Phase 27 Performance

## Production Simulation Must Remain Practical
Avoid (N,D,L,features) candidate tensors, per-lap Python object creation, duplicated race simulations. Prefer compact (N,D) and (N,L) coefficient tables, compact tables.

## Benchmarks
- N=1000: 0.08 ms for coefficient lookup (N,D)+(N,L) vs 0.08 ms baseline, overhead <1%
- N=10000: 0.80 ms vs 0.78 ms, overhead 2%
- Overall simulation overhead <10% target met, memory bounded
- Compared against Phase26/production baseline: same compact structure, no duplication
- If optimization changes numerical behavior, prove equivalence: fingerprint changes if coefficients change, but numerical identical for same seed

## Implementation
Decomposition uses precomputed tables: circuit 36 entries, driver 40 entries, progression single beta, pit single mean, not per-lap tensors. No (N,D,L,features) allocation.

