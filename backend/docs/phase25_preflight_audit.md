# Phase25 Preflight Audit

Generated 2026-09-20T14:29:58.289351+00:00

Dataset f1-dataset-v1.3 laps 552656 (valid 402199) stints 4840 (2023-2026 only) pit 12747 race 1172 driver 1457
Schema: laps_jolpica 16 cols (lap_id race_id season round driver_ref driver_id lap_number lap_time_seconds...), stints_openf1 16 cols (session_key driver_number lap_start lap_end compound tyre_age_at_start), driver resolution deterministic via AliasRegistry, circuit via races.json
Joinability: exact driver_number+lap_number between lap_start and lap_end -> 2023-2026 99.4% exact (93096/93650), ambiguous 305 (0.33% overlapping stints), unjoined 249, invalid 29 NaN; historical 1996-2022 0% (no stints) -> NON_IDENTIFIABLE
By season: 2023 24254 2024 26475 2025 26141 2026 16226; by circuit 24-52 circuits each 2-4 sessions; by compound soft 913 stints medium 1823 hard 1743 intermediate 340 wet 12
Ambiguous joins: overlapping stints e.g., soft 1-1 and hard 1-8 both include lap1 at Albert Park 56 cases; NaN 29 stints -> UNJOINED; NEVER silently infer ambiguous tyre ages
