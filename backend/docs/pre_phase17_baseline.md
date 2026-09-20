# Pre-Phase 17 Baseline

Frozen: 2026-09-17T17:46:24+00:00

Dataset: f1-dataset-v1.1 hash 2cce529c (races 1172, results 26228, seasons 1950-2026)
Calibration: calibration-v1.0.0 hash 3df26222 (909 drivers, top1 0.30, Brier 0.039)
Tyre: tyre-calibration-v1.0.0 hash 503079ee SOFT -0.222 HARD -0.201 GLOBAL -0.207 (associational, fuel-confounded; prior +0.05 stale doc corrected)
Engine: raceengine-v1.2.0 model 0.3.0 simulation 8.2.0
RNG: Level A driver/constructor/qualifying/reliability, Level B AR1 (0.19 win diff, same top driver, Brier 0.001)
Tests: 378 collected 378 passed (incl. 10 perf, 21 tyre)
Benchmark: 10k*58 cold 9.24s warm 4.59s <30s PASS, tyre cold 5.64s warm 2.73s
Leakage: 0 violations strict_before
Fingerprint: N=10 0505d254 exact, N=10000 top same
Status: READY (3 blockers fixed: dataset manifest v1.0->v1.1, tyre hash a1b2c3d4->503079ee, docs 0.07-> -0.222)
