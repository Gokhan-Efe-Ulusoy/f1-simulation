# Phase 23 Preflight Audit

Generated: 2026-09-20T13:26:35.158802+00:00

Dataset: f1-dataset-v1.3, races 2cce529c results 112c8475 laps 552656 pit 12747 stints 4840 weather 13346 race_control 5891
Season coverage 1950-2026, lap coverage 1996-2026 (582 races), pit 333 races, stint compound only 2023+ (4840), weather 2023+ (13346), race_control 2023+ limited
Driver resolution MATCHED 552656 UNMATCHED 0, constructor OK, circuit 99, duplicate 0, orphan 0, leakage 0, missingness: pre-1996 laps NOT_AVAILABLE, tyre pre-2010 NON_IDENTIFIABLE
Impossible lap times <50s filtered, >600s red-flag preserved, lap numbers 1-100 valid, pit anomalies 10-60s total, retired-driver truncated preserved, SC laps >200s excluded from pace, formation/pit/out/in not separately labelled -> PARTIALLY_OBSERVABLE, sprint anomalies handled via round
OBSERVABLE: lap_time (1996+), pit duration total (2004+), driver, constructor, circuit, race progression
PARTIALLY_OBSERVABLE: tyre compound/age (2023+), weather/track temp (2023+), race_control SC/VSC (2023+)
NON_IDENTIFIABLE: exact fuel load, historical tyre pre-2010, historical weather pre-2023, setup, strategy decisions, fuel, sector decomposition where insufficient
