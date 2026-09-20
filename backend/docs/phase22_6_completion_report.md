# Phase 22.6 — Completion Report

## 1. Executive summary

Deep backfill executed with a resumable, rate-respectful runner. **631,124 new
canonical rows across 14 families**; dataset promoted v1.1 → **v1.2** (parent
pinned, backbone hashes unchanged); calibration and simulation frozen.
Jolpica throttling (429→timeout) capped lap coverage at 1996–2001; everything
else completed. `COMPLETE_WITH_LIMITATIONS`.

## 2. Sources researched (≥15, classes A–E)

A (authoritative/direct): jolpica-laps (1996+, probed 1990/94/95 = 0, 1996 R1
total 812), jolpica-pitstops (2011+, 2010 = 0, 2011 R1 = 45), jolpica
results/qualifying/standings/status/circuits/drivers/constructors (1950–2026,
pre-ingested). B (structured secondary): openf1 laps/stints/weather/pit/
race_control/position/overtakes/team_radio/session_result/drivers/intervals
(2023–2026; 2018–2022 = 404, never retried), open-meteo ERA5 (1950–2026, live
OK), f1db pinned v2026.13.0 (local, CC BY 4.0), fastf1 library (AVAILABLE +
cache). C (community, staged-labelled or rejected): kaggle/ergast mirrors → D
(rejected: license/auth). E (reference-only): FIA/F1 official (no scraping).

## 3. Sources acquired

jolpica-laps (99 races), jolpica-pitstops (333 races), openf1 11 endpoints × 84
past Race sessions (+4 sessions discovery files), era5 (558 races). Raw: 2,868
payload files + sha256 sidecars under `data/raw/jolpica/`, `data/raw/openf1/`,
`data/raw/era5/`. Every manifest row carries source/endpoint/season/race/rows/
rejected/failures/rate-limits/missing/schema/sha256/timestamp/license/tier/
canonicalization status (`phase22_6_acquisition_manifest.json`).

## 4. Sources rejected

kaggle mirrors (D); FIA/F1 bulk (E); openf1 car_data/location bulk (sample-only
policy; availability proven: 219 rows/min/driver); openf1 2018–2022 (404).

## 5. Acquisition coverage

laps_jolpica 98,950 (99 races, 1996–2001) · pitstops_jolpica 12,747 (333 races,
2011–2026) · laps_openf1 93,650 · stints 4,840 · weather_openf1 13,346 ·
pitstops_openf1 2,897 · race_control 8,875 · positions 41,365 · overtakes 21,022 ·
teamradio 6,427 · results_openf1 1,705 · drivers_openf1 1,881 · intervals raw
complete/partial-parquet (310,027 rows, 12 partitions, deferred) ·
reanalysis_era5 13,392 (558 races). HTTP failures recovered to 0 (4 transient
429s retried via resume); missing = genuinely absent (future sessions deferred,
6 pit-less + 4 radio-less sessions recorded).

## Era-coverage matrix (quantified, post-22.6)

| family | 1950s–1980s | 1990s | 2000s | 2010s | 2020s |
|---|---|---|---|---|---|
| results | FULL | FULL | FULL | FULL | FULL |
| qualifying | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| laps | NOT_AVAILABLE | LIMITED (1996–99: 49 races) | LIMITED (2000–01: 50 races; 2002–09 gap) | NOT_AVAILABLE | LIMITED (openf1 84 sessions) |
| sectors | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | LIMITED (openf1) |
| pitstops | NOT_AVAILABLE | PARTIAL (legacy parquet) | PARTIAL (legacy) | PARTIAL (legacy + jolpica) | PARTIAL (legacy + jolpica + openf1) |
| stints/tyres | NON_IDENTIFIABLE/PRIOR_ONLY | PRIOR_ONLY | PRIOR_ONLY | PRIOR_ONLY | LIMITED (4,840 stints, observed) |
| weather | PRIOR_ONLY | PRIOR_ONLY | PRIOR_ONLY | LIMITED (ERA5 reanalysis) | LIMITED (sensors + reanalysis) |
| race_control | PRIOR_ONLY | PRIOR_ONLY | PRIOR_ONLY | PRIOR_ONLY | LIMITED (8,875 msgs) |
| telemetry | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | LIMITED (fastf1, un-pulled bulk) | LIMITED (sample policy) |
| positions | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | PARTIAL (41,365 rows) |

FULL is never claimed from a single race: every LIMITED+ cell above is backed
by the row/race counts in §5.

## 6–10. Family coverage

laps: P0 partial (99/≈550 possible Jolpica races; probes prove 1996+ exists —
resume to extend). pitstops: FULL 2011–2026 vs source (plus 1994–2010 legacy
parquet). openf1: 84/84 past Race sessions, all endpoints. weather: 84 sessions
direct + 558 races REANALYSIS. race-control: 84 sessions (8,875 msgs).

## 11. Tyre evidence

4,840 stints, compounds restricted to observed {soft, medium, hard,
intermediate, wet} + source-native labels via deterministic map; unknown →
empty + warning (tested). No compound inferred from pits/laptime/regs (tested).
Tier: LIMITED candidate; coefficients untouched.

## 12. Source reconciliation

`phase22_6_source_reconciliation.md`: pits 299/322 exact count agreement (A),
5,998/6,006 value agreement <2 ms (A, confirming old column = total duration);
deltas explained (stale snapshot, in-progress 2026); laps JvO scope gap stated;
lap-1 offset re-affirmed; driver resolution 111,697/111,697 deterministic.

## 13. Conflicts

pit counts: 23 races (B ±1, C stale-snapshot); values: 0 genuine (8 null-side
uncomparable, E). lap-1 systematic offset persists (C, 22.5 record stands).
No silent overwrites anywhere.

## 14. Data quality

`phase22_6_lap_quality_report.md`: 0 dup PKs, 0 nulls, 0 impossible laps, 6
red-flag laps classified-not-removed, 151 retirement-truncation slots
documented. Pit stats: median 23.580 s, p05–p95 18.77–46.72 s;
PIT_DURATION_OBSERVED / PIT_LOSS_NOT_IDENTIFIABLE.

## 15. Leakage audit

All families carry observed/retrieved dates; race-date precision marked;
`observation < ingestion` asserted (tested); future sessions deferred, never
ingested; walk-forward rule unchanged. **violations = 0.**

## 16. Provenance audit

Every canonical row: source, version, retrieved_at, source_record_id,
raw_sha256, evidence_tier, canonicalization_version 22.6.1. 2,800+ sidecars
verify (tested). One corrupt payload found + quarantined (Open-Meteo 200-with-
error-string; validator added; file re-fetched valid).

## 17. Dataset version decision

**v1.2 minted** (parent v1.1): backbone files byte-identical (races 2cce529c,
results 112c8475 re-verified, tested); +631,124 rows in 14 new families;
manifest `dataset-manifest-v1.2.json` + registry entry. v1.1 files untouched.

## 18. Calibration promotion decision

**FROZEN.** New fields classified: NEW (laps 1996–2001, openf1 families,
reanalysis), DUPLICATE (pitstops vs old parquet), CONFLICT (23 races, measured),
LIMITED (stints/weather/RC), CALIBRATION_CANDIDATE (pit distribution, tyre,
weather-lap, sector/driver pace — era-scoped, future phase only),
NON_IDENTIFIABLE (setup/strategy/fuel/pit-loss split). No coefficient changed.

## 19. Performance/storage

Raw ≈ 340 MB (openf1 290 MB incl. intervals), parquet ≈ 60 MB; disk free 166 GB.
Acquisition: ~1.2–4 s spacing, backoff, resume; canonicalization streaming,
bounded memory. Simulation code untouched → performance unchanged.

## 20. Test results

31 new tests (`test_phase22_6_backfill.py`), all green. Full suite `pytest -q`
(2026-09-19): **691 passed** (660 pre-existing + 31 new), 0 failed, ~24 min.
No existing test modified; no simulation behavior change (model code untouched,
replay fingerprints intact by construction — dataset consumers pin versions).

## 21. Limitations

- Jolpica laps 2002–2026 not backfilled (429/timeout throttle after ~1500
  sustained requests; resume: `--laps-only --start 2002 --end 2026 --rate 3 --resume`).
- intervals parquet deferred (12/84; raw complete).
- Pit lane/stationary split NON_IDENTIFIABLE everywhere.
- ERA5 ≠ sensors; telemetry bulk not pulled; setup/strategy/fuel NON_IDENTIFIABLE.
- 2026 season in progress: counts move; old snapshot deltas documented.

## 22. Future research

Resume laps backfill → circuit/era pit-loss distributions → stint-joined tyre
degradation with fuel proxy → session-aligned weather-lap effects → SC/VSC
rates once N suffices → dedicated calibration phase (only then promote).
