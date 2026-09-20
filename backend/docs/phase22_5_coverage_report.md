# Phase 22.5 — Coverage Report (before → after)

Machine-readable: `backend/data/manifests/external_coverage.json`.
Canonical version unchanged: `f1-dataset-v1.1`. "Acquired" = staged rows
(`data/external_staging/`); canonical promotion requires the gate (§20)
and did NOT happen this phase.

| Variable | Current (canonical) | Acquired (staged) | Canonical | Coverage change |
|----------|---------------------|-------------------|-----------|-----------------|
| Race results | FULL | 0 | unchanged | no change |
| Qualifying | PARTIAL | 0 | unchanged | no change |
| Lap timing | LIMITED | 2258 | STAGED, canonical unchanged | +2258 rows, 2024 Bahrain (Jolpica 1129 + OpenF1 1129), era 2022–2026 |
| Sector timing | LIMITED | 1127 | STAGED, canonical unchanged | +1127 OpenF1 laps with S1/S2/S3, 2024 Bahrain |
| Pit timing | PARTIAL | 235 | STAGED, canonical unchanged | +192 Jolpica (2024 R1–R5) +43 OpenF1; modern rows where canonical had only sparse 1950s–1990s |
| Tyre compound | LIMITED | 63 | STAGED, canonical unchanged | +63 observed compounds (OpenF1 stints, 2024 Bahrain) |
| Tyre age | PRIOR_ONLY | 63 | STAGED, canonical unchanged | +63 observed ages-at-start → LIMITED candidate in 2022–2026 only |
| Weather | LIMITED | 157 (+144 reanalysis) | STAGED, canonical unchanged | +157 session sensors (2024 Bahrain) +144 ERA5 hourly (6 races, REANALYSIS-labeled) |
| Race control | LIMITED | 71 | STAGED, canonical unchanged | +71 timestamped messages (2024 Bahrain), flag taxonomy observed |
| Telemetry | LIMITED | 0 | unchanged | no change (sample policy; endpoint documented) |
| Setup | NON_IDENTIFIABLE | 0 | unchanged | no change — no source exists |
| Strategy | NON_IDENTIFIABLE | 0 | unchanged | no change — decisions unobservable |
| Regulation | LIMITED | 321 | evidence layer (not canonical) | +321 rows (`data/regulations/regulation_evidence.json`), all eras |

## Era analysis (observable variables per era after this phase)

- **1950–1969 … 2000–2009**: race results FULL, qualifying PARTIAL, pit PARTIAL
  (sparse), regulation evidence present. Lap/tyre-age/weather/RC/telemetry:
  PRIOR_ONLY or NOT_AVAILABLE — unchanged, no source found.
- **2010–2017**: + Jolpica pit durations (endpoint starts ~2011) and lap rows
  (probes confirm lap rows back to 1996; pagination of these eras is future work).
- **2018–2021**: + FastF1-available timing/telemetry (library AVAILABLE, cache
  present; not bulk-pulled this phase).
- **2022–2026**: all acquisitions above. Tyre age upgrades PRIOR_ONLY →
  LIMITED *candidate* in this era only; all other eras keep prior tiers.
  No era was relabeled in canonical — staging only.

## What did NOT improve (honest)

Pre-1996 lap timing, pre-2011 pit timing, pre-2023 tyre/weather/RC at lap
resolution, any-era telemetry bulk, setup, strategy, qualifying sessions:
zero new observations. The simulator remains era-aware-or-honest, not
pretending modern data exists historically.
