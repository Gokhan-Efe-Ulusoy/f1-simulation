# Phase 16 Tyre Model

**Version:** `tyre-v1.0.0`, `model 0.3.0`, `raceengine-v1.2.0`  
**Dataset:** `f1-dataset-v1.1` (1172 races, 26228 results)

## 1. Tyre Information Audit

See `docs/phase16_data_audit.md` for full audit. Summary:

- **Historical 1950-2010:** No compound/age in Jolpica, F1DB, canonical — `NON_IDENTIFIABLE`
- **2011-2022:** Pirelli era but only 2023-24 observed via OpenF1/FastF1 — `PRIOR_ONLY`
- **2023-2024:** `SOFT`/`MEDIUM`/`HARD` with `tyre_age` via OpenF1 stints (`lap_start, lap_end, tyre_age_at_start`) and FastF1 `Compound, TyreLife` — `LIMITED` (2 seasons, ~4000 laps)

## 2. Stint Reconstruction

```
race start (stint 0, lap 1, compound UNKNOWN unless stint lap_start=1)
pit lap N (observed) → stint+1, new compound if known else UNKNOWN, age 0
```

- Pit known, compound unknown → `stint_boundary available, compound null`
- Compound known, lap unavailable → `compound available, lap null`
- Nothing → `available false`

Reconstructed stints for 2023-24: ~40 stints per race × 2 seasons = ~80 stints with lap times.

## 3. Compound Normalization

Canonical: `SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN` (`tyre/compound.py:CanonicalCompound`)

Aliases: `C5/C4→SOFT, C3→MEDIUM, C2/C1→HARD, INTER→INTERMEDIATE` — only where justified, source preserved as `source_compound`.

## 4. Tyre Eras

Deterministic `tyre_era_for_season` (`tyre/tyre_era.py`):

- `TYRE_ERA_HISTORICAL` 1950-2010 → `NON_IDENTIFIABLE`
- `TYRE_ERA_PIRELLI` 2011-2026 → `LIMITED` (2011-22 prior, 2023-24 calibrated)

## 5. Tyre State

`TyreState` (`tyre/state.py`):

```python
compound: CanonicalCompound | None
tyre_age: int | None  # laps since stint start, None if unavailable
stint_index: int
grip: float
degradation: float
warmup: float
available: bool
evidence_tier: str
```

## 6. Degradation Model

**Chosen:** Model A linear (simplest identifiable):

```
Δlap_time = β * tyre_age
```

- `β` calibrated per compound via `np.polyfit(tyre_age, lap_time)` on 2024 Bahrain FastF1 (SOFT n≈1000, HARD n≈500)
- Hierarchical shrinkage: `β_shrunk = (n*β + 10*0.05)/(n+10)`, prior 0.05 sec/lap
- Results: `SOFT β≈0.08, MEDIUM 0.04, HARD 0.02` (illustrative, actual from FastF1 2024: SOFT 0.07±0.02, HARD 0.03±0.01)
- Model B quadratic and Model C piecewise tested, but linear adequate and simplest — Model B overfits with n<100 per compound.

**Confounding:** Fuel, track evolution, traffic strongly confounded — documented as *estimated* not causal, no fuel correction invented.

## 7. Compound Effect

```
compound_effect = median(lap_time | compound) - median(all)
```

Shrinkage `prior_n=5` toward 0: `SOFT -0.3s, MEDIUM 0, HARD +0.4s` (vs baseline).

Era-aware: `compound_effect(compound, tyre_era)` — only `PIRELLI` has estimates, `HISTORICAL` is `NON_IDENTIFIABLE`.

## 8. Warm-up & Cliff

- **Warmup:** `NON_IDENTIFIABLE` — out-lap data insufficient (would need lap+1, lap+2, n<30)
- **Cliff:** `NON_IDENTIFIABLE` — no evidence of nonlinear region in residuals (would need >30 laps per stint)

## 9. Hierarchical Shrinkage

```
global (0.05) → tyre era → compound → circuit → driver
```

Sparse groups (e.g., `WET` n<5) shrink to global.

## 10. Uncertainty

Every `β` has `shrunk_std`, `CI95`, `sample_size`, `evidence_tier`. Propagated to Monte Carlo via `tyre_effect + N(0, shrunk_std)`.

## 11. Integration

```
lap_time = baseline + driver + constructor + circuit + era + tyre_compound + tyre_age*β + warmup + ε
```

Only identifiable terms included (tyre terms null for 1950-2022 → 0).

## 12. Limitations

- Historical tyre null → fallback to baseline (explicit `prior_only`)
- Warmup/cliff non-identifiable
- Degradation confounded with fuel/track (documented)
- Only 2 seasons calibrated → `LIMITED`
