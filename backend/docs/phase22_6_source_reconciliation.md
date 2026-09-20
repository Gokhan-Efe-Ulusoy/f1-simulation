# Phase 22.6 — Source Reconciliation

Rule: where two sources describe the same observation, both are preserved and
the disagreement is classified. Nothing is overwritten.

## Classes

A exact agreement · B harmless representation difference · C systematic offset ·
D material conflict · E unresolved/excluded.

## P1. Pit stops: canonical `pit_stops.parquet` vs new `pitstops_jolpica/`

- 322 races present in both. **299 exact stop-count agreement (A).**
- 23 count differences (B/C): ±1 stop in ~10 races (representation: stop-number
  attribution on shared-drive/retirement laps); larger deltas are stale-snapshot
  effects, all in the same direction (live API newer than the v1.1 snapshot):
  2025-canada new 82 vs old 33 (wet-chaos race, snapshot predates full data),
  2026 in-progress races (monaco −58, zandvoort −23, monza −12: season still
  running, v1.1 snapshot older). 2026-madring present only in the old file's
  schedule area (E: scheduled, no source data anywhere yet).
- 288 races only in old file: 1994–2010, pre-Jolpica-pits era (expected gap,
  not a conflict). 1 race only in new file (recent round absent from snapshot).
- Value check on 6,006 matched (race, driver, lap) pairs:
  **5,998 agree < 2 ms (A)** between old `stationary_time_seconds` and new
  `duration_seconds` — confirming the old column is the Ergast total duration,
  NOT a stationary split (column semantics recorded; future rename, no rewrite).
  8 pairs uncomparable (null new duration, E) + 14 null durations total in the
  new family (source gaps with time_of_day preserved, e.g. 2011-hungary webber
  lap 25). Missingness preserved, never imputed.
- Verdict: new family is DUPLICATE (counts/values) + ENRICHMENT (`time_of_day`,
  `stop_number`, `observed_date`, full provenance). No double counting:
  canonical consumers must pick one family per analysis (documented in v1.2 manifest).

## P2. Lap times: Jolpica vs OpenF1

- No overlapping coverage in the new backfill (Jolpica laps 1996–2001,
  OpenF1 laps 2023–2026) → no new comparison possible (honest scope limit).
- The Phase 22.5 finding stands and is re-stated: 2024 Bahrain, 20/1129 lap-1
  pairs differ 0.317–0.510 s systematically (C: start-line definition), laps
  2–57 agree < 2 ms (A). The offset remains explicitly represented in
  `external_conflicts.json` (pattern `systematic_single_lap_offset`).

## P3. Driver identity reconciliation

- 121 distinct Jolpica driver refs across the backfill → canonical: **111,697
  rows MATCHED, 0 AMBIGUOUS, 0 UNMATCHED** after exact-alias + unique-token +
  season-presence disambiguation (all deterministic, in
  `app/data/external/resolution.py`). Season filter uses canonical results as
  evidence (e.g. `villeneuve` 1996 → jacques-villeneuve). Unresolvable refs
  would keep `driver_id` null with `driver_ref` preserved — zero occurred.

## P4. OpenF1 internal consistency

- 84/84 past Race sessions yield laps+stints+weather+race_control+positions+
  overtakes+session_result+drivers; 78 pit, 80 team_radio (6/4 sessions with no
  endpoint data = missing, recorded in checkpoint, not fabricated).
- 1 orphan session (date unmatched to canonical schedule — recorded in
  canonical manifest, `race_id` empty, never joined).
