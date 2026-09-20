# Tyre Join Layer

Join key race_id+driver_number+lap_number between lap_start and lap_end deterministic via resolve_lap, confidence EXACT 93096 DETERMINISTIC 0 AMBIGUOUS 305 UNJOINED 249 INVALID 0
Total laps 93650 exact 93096 (99.4%) filtered for calibration 88617, coverage by season {'2023': 24254, '2024': 26475, '2025': 26141, '2026': 16226}, by compound {'': 85, 'hard': 44365, 'intermediate': 4111, 'medium': 33376, 'soft': 11078, 'wet': 81}
Provenance: race_id season round driver_ref canonical driver_id lap_number stint_id compound tyre_age stint_lap join_confidence evidence_tier source_reference, reproducible via tyre_join-v1.0.0 seed 42 as_of strict
Only EXACT/DETERMINISTIC may enter causal calibration; AMBIGUOUS/UNJOINED visible but not silently dropped
