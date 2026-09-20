# Phase 17 Weather Model

**Version:** `weather-v1.0.0`, `MODEL_VERSION 0.4.0`, `raceengine-v1.3.0`
**Status:** Modular, uncertainty-aware, deterministic, prior-only where insufficient evidence.

## 1. WeatherState Model

Canonical state `app/simulation/weather/state.py:WeatherState`:

| Field | Unit | Range | Tier (historical 1950-2022) | Tier (2024-03-02) |
|-------|------|-------|-----------------------------|-------------------|
| `air_temperature_c` | °C | [-10,50] | NON_IDENTIFIABLE | LIMITED (openf1 n~644) |
| `track_temperature_c` | °C | [-5,65] | NON_IDENTIFIABLE (estimated +10) | LIMITED |
| `humidity_pct` | % | [0,100] | NON_IDENTIFIABLE | LIMITED |
| `pressure_hpa` | hPa | [900,1100] | NON_IDENTIFIABLE | LIMITED |
| `wind_speed_mps` | m/s | [0,50] | NON_IDENTIFIABLE | LIMITED |
| `wind_direction_deg` | ° | [0,360] | NON_IDENTIFIABLE | LIMITED |
| `rainfall_mm_h` | mm/h | [0,100] | NON_IDENTIFIABLE | OBSERVED (0 when dry) |
| `track_wetness` | 0-1 | [0,1] | PRIOR_ONLY (0 dry) | PRIOR_ONLY (derived) |
| `weather_regime` | enum | DRY/DAMP/WET/HEAVY_RAIN/DRYING | derived | derived |
| `visibility_km` | km | [0,20] | PRIOR_ONLY | OBSERVED via condition |

All fields have validation (`ge`, `le`), evidence tier per field, provenance, deterministic serialization `model_dump()`.

Existing `app/simulation/models/weather.py` (Phase 7) kept for compatibility; new `weather/state.py` is canonical.

## 2. Regimes

`app/simulation/weather/regime.py:WeatherRegime`:

```
DRY:       wetness <=0.01 and rain==0
DRYING:    0.01 < wetness <=0.1 and rain==0
DAMP:      0.1 < wetness <0.5 or light rain+low wetness
WET:       wetness >=0.5 or rain>0 with wetness
HEAVY_RAIN: rainfall >=7.5 mm/h
```

Derived from `WeatherState` deterministically (`derive()`), not arbitrarily chosen downstream.

## 3. Wetness Model

`app/simulation/weather/environment.py:WetnessModel`:

```
wetness(t+1) = clamp( wetness(t) + rainfall_mm_h * 0.01 - drying_rate , 0,1 )

drying_rate = base(0.02)
            * (1 + wind*0.02)
            * (1 + max(0,track_temp-20)*0.01)
            * traffic_factor (≈1.0-1.5)
            * humidity_penalty( high humidity slows)
```

Bounds `[0,1]`. Shared race-level, not per-driver.

## 4. Rainfall Intensity

```
NONE:     0
LIGHT:    0 < 2.5
MODERATE: 2.5-7.5
HEAVY:    >=7.5 mm/h
```
Not FIA official, documented.

## 5. Transitions

`app/simulation/weather/transition.py:WeatherTransitionModel`:

Persistent, not independent random per lap:
- Temperature drift `N(0,0.2)*volatility` per lap
- Humidity `N(0,1.0)`, wind `N(0,0.5)`, pressure `N(0,0.3)`
- Rainfall start prob `base 0.01 + humidity/100*0.05 + (1000-pressure)*0.0002 + cloud*0.02` capped 0.15, scaled by volatility → ~0.001 per lap dry (∼5% wet races)
- Rainfall stop prob `0.05*(1 - rainfall/20)`
- Wetness via `WetnessModel.step`

Deterministic given `rng = np.random.default_rng(seed + sim_idx*1000 + 500 + lap)` (isolated stream).

## 6. Air → Track Temperature

Distinct fields, not `track = air`. If `track_temperature_c` missing:
```
T_track = T_air + 10  (empirical Pirelli)  evidence ESTIMATED
```
Linear coefficient not calibrated (sample <30 paired pre-as_of), so `NON_IDENTIFIABLE` for historical, `ESTIMATED` with wide uncertainty for modern.

## 7. Evidence Tiers

Reuse project tiers: `OBSERVED / CALIBRATED / ESTIMATED / PRIOR_ONLY / NON_IDENTIFIABLE`. Every variable traceable per field.

## 8. Uncertainty & Forecast

`weather/forecast.py`, `uncertainty.py`:

- Forecast: `WeatherForecast(issue_time, predicted_states, rain_prob, confidence_decay 0.05/lap)`
- Observed vs forecast vs simulated distinct.
- Stochastic components documented (temp drift, etc.), propagated via isolated weather RNG into Monte Carlo.
- No arbitrary global Gaussian on every variable.

## 9. Versioning

Weather model `weather-v1.0.0`, calibration `weather-calibration-v1.0.0` (prior-only). No dataset version bump.

## 10. Limitations Honestly Stated

- Historical 1950-2022: all weather `NON_IDENTIFIABLE` (0-2 obs, not fabricated)
- Modern 2023-2026: ~644 OpenF1 observations (4 sessions) → most vars `LIMITED` (n<100 per circuit), `CALIBRATED` only globally pooled
- Wet race n≈2-3 <30 → wet performance, temperature effects remain `PRIOR_ONLY`
- No causal claim: associational `grip(wetness)` only, with prior coefficients.

## 11. Chain

```
DATA (openf1 644) → WeatherState(t) → Transition → TrackEnvironment(t) → TyreEnvironment(t) → Grip(t) → LapTime(t) → Incident(t) → Strategy(t) → Outcome
```
Each arrow testable, deterministic, versioned, uncertainty-aware where supported; otherwise NON_IDENTIFIABLE.
