# Phase 32 — Provenance & Evidence

- `EvidenceBadge` maps backend tiers verbatim: CALIBRATED, LIMITED, PRIOR_ONLY, PROXY_ONLY, NON_IDENTIFIABLE, ASSOCIATIONAL (+UNKNOWN fallback). Tested that NON_IDENTIFIABLE never renders as KNOWN/CALIBRATED/OBSERVED.
- `SimulationProvenance` shows only returned fields: simulation/job ID, seed, race, N, dataset/model versions, request/result hashes. Nothing invented.
- Weather/setup modifiers labeled hypothetical/PRIOR_ONLY; fuel NON_IDENTIFIABLE stated in UI copy. Comparison explicitly "observed differences only — not causal attribution".
