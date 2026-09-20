# Phase 22.5 — Completion Report

## Status

```
PHASE_22_5_STATUS = COMPLETE_WITH_LIMITATIONS
```

Pipeline works end to end on real data; acquisition is a high-value slice
(single-race depth + 5-race pits + 6-race reanalysis), not a full backfill.
All claims below are verified against manifests/staging/raw on disk.

## Answers (§33)

1. **Sources discovered:** 15 (catalog + `external_sources.json`).
2. **Actually downloaded:** 9 live (jolpica-laps/pitstops/results, openf1
   timing/stints/weather/pit/racecontrol, openmeteo-era5) + 2 local-evidence
   (f1db pinned release, fastf1 cache probe) = 11 acquired; 32 raw files.
3. **Rejected/blocked:** 1 REJECTED (ergast-mirror-kaggle: license unverified +
   auth) + 2 BLOCKED/reference-only (fia-documents, official-f1-timing: no
   bulk endpoint / ToS).
4. **Primary/official:** FIA + F1 official documented as reference-only; all
   acquired data is PRIMARY_OPEN_DATA / REPUTABLE_SECONDARY / VERIFIED_RESEARCH.
5. **New variables acquired:** lap times, sector times, speed traps, pit
   durations, observed compounds, observed tyre ages, session weather,
   race-control messages, hourly reanalysis weather, regulation evidence rows.
6. **Observations added:** 2928 staged rows (0 canonical — staging only).
7. **Years improved:** 2024 (staging depth); probes confirm 1996+ laps /
   2011+ stops exist for future backfill.
8. **Circuits improved:** Bahrain (depth), Jeddah/Melbourne/Suzuka/Monaco/
   Silverstone (pits and/or reanalysis weather).
9. **Lap timing:** +2258 staged rows (2024 Bahrain, dual-source).
10. **Pit stops:** +235 staged modern rows (canonical had only sparse 1950s–1990s).
11. **Tyre:** +63 stints with observed compound AND age (age was PRIOR_ONLY).
12. **Weather:** +157 session-sensor rows +144 reanalysis hours.
13. **Race control:** +71 timestamped messages with flag taxonomy.
14. **Telemetry:** +0 (documented, sample policy; endpoint gated-allowed).
15. **Remain NON_IDENTIFIABLE:** setup, strategy (no source exists).
16. **Remain PRIOR_ONLY:** SC/VSC probabilities, qualifying/circuit pace,
    pit-loss split/mean (24.4 s), fuel effects, telemetry bulk.
17. **Calibration candidates (LIMITED, era 2022–2026 only):** pit_loss,
    tyre_degradation, weather_lap_effect, sector_pace, driver_pace
    (+ lap/sector/compound/age/weather/RC promotion candidates in gate).
18. **Conflicts:** 20 genuine (1.77%) — systematic lap-1 definition offset,
    both sources preserved, canonical untouched.
19. **Canonical changed:** NO. Dataset `f1-dataset-v1.1` unchanged.
20. **Dataset version:** unchanged (`f1-dataset-v1.1`; staging only).
21. **Calibration version:** unchanged (`calibration-v1.0.0`; no recalibration).
22. **Simulation behavior:** unchanged (no model code touched).
23. **Tests:** new `test_phase22_5_external.py` (44 tests) green; full suite
    `pytest -q`: **660 passed** (616 pre-existing + 44 new), 0 failures.
    No existing test logic modified (one legacy module relocated verbatim:
    `app/data/regulations.py` → `app/data/regulations/curated.py` with
    re-export package; required because the new evidence schema occupies
    `app/data/regulations/`).
24. **Licensing/restrictions:** Kaggle mirrors (unverified/auth), FIA/F1
    (no endpoint/ToS), OpenF1 live (paywall — historical used), free-API
    rate limits (1.5 s spacing, pagination caps). All honored.

## Deliverables

Docs (8): source_catalog, data_acquisition, data_audit, conflict_audit,
coverage_report, calibration_readiness, limitations, completion_report
(this file). Manifests (4): external_sources, external_acquisition_manifest,
external_conflicts, external_coverage. Pipeline: `app/data/external/`
(11 modules) + `app/data/regulations/` + `scripts/phase22_5_acquisition.py`.
Staging: 8 tables. Calibration candidates: 9 files. Regulation evidence:
321 rows. Tests: 44 new, 660 total green.

## Test gate (§35)

`pytest -q` (backend/, 2026-09-19): **660 passed in ~23.5 min**, 0 failed.
Acquisition/data slice (`test_phase22_5_external.py`): 44/44 green.
