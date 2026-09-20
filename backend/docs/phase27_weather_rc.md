# Phase 27 Weather & Race Control

## Weather
Use only observed weather data, separate sensor/observed vs ERA5 reanalysis vs prior-only, do not mix silently.

- Observed modern via weather_openf1 84 files: sensor data air_temp, track_temp, humidity, pressure, rainfall, wind
- ERA5 reanalysis 558 races *24 rows: reanalysis not sensor, prior-only
- For observed modern investigated rainfall, wetness, temperature but do NOT promote coefficient if sample insufficient, walk-forward unstable, circuit confounding dominates
- Result:
  - Wet laps in filtered valid set: 0 (because filtered to hard/medium/soft only; unfiltered wet 81 + intermediate 4111)
  - Using all laps: wet 4192, dry 88616? Actually filtered set excludes wet, so observed wet insufficient n<50 => PRIOR_ONLY
  - Dry vs wet effect not calibrated, tier PRIOR_ONLY
  - As_of race_date -1 day respected, realized future weather not used
  - Circuit confounding dominates: wet mostly at specific circuits (e.g., spa), small n

## Race Control
Use Phase18 race-control states, only where observations exist.

Possible states: GREEN, YELLOW, DOUBLE_YELLOW, VSC, SAFETY_CAR, RED_FLAG, RESTART

- GREEN n85288 mean 90.85 CALIBRATED
- YELLOW n3263 mean 103.2 CALIBRATED
- RED_FLAG n66 mean 152.47 LIMITED
- SAFETY_CAR/VSC 0 in enriched valid because rc_map did not capture SC flag strings correctly; actual SC/VSC historical 222 laps per phase26, but in filtered valid 0 => PRIOR_ONLY
- Because historical coverage limited (only 2023-2026 84 sessions) SC/VSC historical effects remain PRIOR_ONLY unless passes gate 100 laps
- Do NOT infer historical SC from modern and label historically calibrated
- Do not introduce future race-control state

## Combined
Both weather and race control remain PRIOR_ONLY/LIMITED not CALIBRATED, not promoted.

