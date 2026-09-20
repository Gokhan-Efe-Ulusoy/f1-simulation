# Phase 22.5 — Limitations (honest, load-bearing)

1. **Single-race depth.** Lap/sector/stint/weather/RC evidence is 2024 Bahrain
   (+ pits R1–R5, reanalysis ×6). One circuit cannot support circuit effects,
   and single-race N cannot support SC/VSC probabilities. Candidates are
   scoped to era 2022–2026 and mostly to one venue.
2. **Pit-loss split still missing.** Neither Jolpica nor OpenF1 splits
   stationary vs pit-lane loss. The 24.4 s prior stays PRIOR_ONLY; the new
   data supports a *total-loss distribution*, not the split.
3. **Lap-1 definition gap.** Jolpica vs OpenF1 lap 1 differs by 0.3–0.5 s
   systematically (start-line definition). Future calibration must exclude or
   offset-model lap 1 (recorded in conflict audit).
4. **Reanalysis ≠ observation.** ERA5 weather is an ~11 km grid, hourly, with
   no track temperature. It bounds weather priors; it does not replace
   session sensors (present only for 2024 Bahrain here).
5. **No telemetry bulk.** `/car_data` sampled at 3.7 Hz was deliberately not
   pulled (volume + rate etiquette). Telemetry stays LIMITED-by-prior-work.
6. **Historical eras unimproved.** 1950–1995 laps, pre-2011 stops, pre-2023
   sectors/tyres/weather/RC remain unobservable from any legal source found.
   Jolpica probes suggest 1996+ laps and 2011+ stops exist — pagination of
   those eras (thousands of rate-limited requests) is future work.
7. **Kaggle mirrors rejected.** ~600k laps / ~22k stops claimed by community
   mirrors were NOT ingested: per-file licenses unverified, FK schemes
   divergent, provenance second-hand. Revisit only with pinned hashes +
   per-dataset license clearance.
8. **Official sources reference-only.** FIA/F1 have no bulk endpoints; no
   scraping was performed (ToS). Regulation evidence is curated extraction
   with confidence scores, not coefficients.
9. **No promotion, no recalibration.** Staging only. Dataset stays
   `f1-dataset-v1.1`, calibration stays `calibration-v1.0.0`, simulation
   behavior is bit-unchanged. Any future promotion must pass the gate per
   variable per era with conflict-rate and missingness bars.
10. **Rate-limit fragility.** Free APIs 429 under load; the runner pages
    cautiously (1.5 s spacing, 12-page/2000-offset caps) and resumes from
    immutable raw. Wider backfills must keep this etiquette.
