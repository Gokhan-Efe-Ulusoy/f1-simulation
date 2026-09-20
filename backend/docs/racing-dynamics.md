# Racing Dynamics Layer Documentation

## 1. Architecture Overview

The Racing Dynamics Layer provides a modular, deterministic framework for simulating wheel-to-wheel Formula 1 racing. It consists of six independent models that integrate into the RaceEngine without mutating global state directly.

```
RaceEngine
|
+-- LapSimulator (existing)
+-- StrategyEngine (existing)
+-- IncidentModel (existing)
+-- OvertakeEngine (NEW)
+-- BattleEngine (NEW)
+-- DirtyAirModel (NEW)
+-- DRSTrainModel (NEW)
+-- DefenseModel (NEW)
+-- SafetyCarRestartModel (NEW)
+-- Event System (extended)
```

### Design Principles

- **No global state mutation**: Models return decisions/effects; RaceEngine applies them
- **Determinism**: All randomness uses named streams from RandomProvider
- **Interpretability**: Every coefficient is named, documented, and unitless (or has explicit units)
- **Statistical validity**: Relationships hold over large samples (verified by statistical tests)
- **Modularity**: Each model can be tested and calibrated independently

---

## 2. Overtake Model

### 2.1 OvertakeContext

Contains all information needed for an overtake decision:

| Field | Type | Description |
|-------|------|-------------|
| attacker_id, defender_id | str | Driver identifiers |
| attacker_position, defender_position | int | Grid positions |
| gap | float | Time gap (seconds) |
| relative_pace | float | Attacker pace - defender pace (sec/lap, negative = attacker faster) |
| tyre_delta | float | Pace advantage from tyre difference (sec/lap) |
| drs_available | bool | DRS activation status |
| attacker_overtaking_skill | float | 0-100 scale |
| defender_defensive_skill | float | 0-100 scale |
| attacker_aggression | float | 0-100 scale |
| track_overtaking_difficulty | float | 0-1 normalized |
| dirty_air_effect | float | Performance loss from dirty air (sec/lap) |
| weather, track_wetness | str, float | Conditions |
| attacker_damage, defender_damage | float | 0-1 combined damage |
| safety_car_active, vsc_active | bool | Race state flags |

### 2.2 OvertakePhase State Machine

```
NO_OPPORTUNITY
    ↓
CLOSING (gap > 0.8s)
    ↓
WITHIN_ATTACK_RANGE (gap 0.2-0.8s)
    ↓
OVERTAKE_OPPORTUNITY (gap < 0.2s)
    ↓
OVERTAKE_ATTEMPT
    ↓
SUCCESS / FAILURE / INCIDENT
```

### 2.3 Probability Calculation

Uses logistic regression on interpretable factors:

```
logit = base_probability + Σ(coeff_i × factor_i)
probability = 1 / (1 + exp(-logit))
```

#### Factors (positive = increases probability)

| Factor | Coefficient | Unit |
|--------|-------------|------|
| pace_advantage | 1.5 | per sec/lap |
| tyre_delta | 2.0 | per sec/lap |
| straight_line_advantage | 1.0 | per sec/lap |
| overtaking_skill | 0.015 | per skill point |
| defending_skill | -0.012 | per skill point |
| aggression | 0.008 | per aggression point |
| drs_enabled | 0.25 | base bonus |
| ers_overtake | 0.15 | bonus |
| ers_high | 0.08 | bonus |
| corner_type (hairpin) | 0.3 | modifier |
| corner_type (slow) | 0.2 | modifier |
| track_difficulty | -1.5 | per 0-1 difficulty |
| dirty_air | -1.5 | per sec/lap |
| wet_weather | -0.4 | penalty |
| damp_weather | -0.2 | penalty |
| damage | -0.5 | per 0-1 damage |
| traffic_ahead | -0.15 | penalty |

Probability clamped to [0.0, 0.85].

### 2.4 Statistical Expectations (Verified)

| Variable | Expected Relationship |
|----------|----------------------|
| ↑ pace advantage | ↑ overtake probability |
| ↑ tyre delta | ↑ overtake probability |
| DRS enabled | ↑ overtake probability |
| ↑ defending skill | ↓ overtake probability |
| ↑ track difficulty | ↓ overtake probability |
| Heavy rain | ↓ overtake probability |
| ↑ aggression | ↑ overtake probability & ↑ incident risk |

---

## 3. Battle Model

### 3.1 BattleStateType

```
NO_BATTLE → CLOSING → WITHIN_DRS → ATTACKING → SIDE_BY_SIDE → OVERTAKE_COMPLETED / BATTLE_ENDED
                    ↓
               BATTLE_ENDED (gap > 3.0s or >10 laps)
```

### 3.2 BattleContext

Tracks persistent state across laps:
- Current gap, min/max gap
- Laps active, DRS availability laps
- Attack attempts, successful overtakes, incidents

### 3.3 State Transitions

| From | To | Condition |
|------|-----|-----------|
| CLOSING | ATTACKING | gap ≤ 0.9s |
| WITHIN_DRS | ATTACKING | gap ≤ 0.9s |
| WITHIN_DRS | CLOSING | gap > 1.0s |
| ATTACKING | SIDE_BY_SIDE | gap ≤ 0.2s |
| ATTACKING | CLOSING | gap > 1.1s |
| SIDE_BY_SIDE | BATTLE_ENDED | 3 laps timeout |
| Any | BATTLE_ENDED | gap > 3.0s or laps > 10 |

### 3.4 Incident Risk

Base risk increases with battle duration. Multipliers:
- Side-by-side: ×2.5
- Aggressive defense: ×2.0
- Defensive defense: ×1.3
- Attacker aggression: ×(1 + aggression/100 × 0.5)
- Wet weather: ×1.5-2.0

---

## 4. Dirty Air Model

### 4.1 Physics Approximation

**This is a statistical/engineering approximation, NOT CFD.**

Smooth distance-dependent function avoids discontinuities:

```
distance_factor = (following_distance / 1.0s) ^ (-1.5)

At 0.5s: ~2.8x effect
At 1.0s: 1.0x (reference)
At 2.0s: ~0.35x
At 3.0s: ~0.19x
```

### 4.2 Total Pace Loss Components

| Component | Base Value | Scaling |
|-----------|------------|---------|
| Cornering loss | 0.15 sec/lap | × distance_factor × aero_sens × corner_mod × weather |
| Braking loss | 0.05 sec/lap | × distance_factor × aero_sens × corner_mod × weather |
| Tyre temp increase | 3.0 °C | × distance_factor × weather |
| Degradation multiplier | 1.15 | 1.0 + 0.15 × distance_factor × weather |

### 4.3 Corner Type Modifiers

| Corner | Modifier |
|--------|----------|
| Hairpin | 1.5 |
| Slow | 1.3 |
| Medium | 1.0 |
| Fast | 0.7 |
| High-speed | 0.5 |
| Chicane | 1.2 |
| Double apex | 1.1 |

Weather reduces dirty air effect: wet = 0.6x

---

## 5. DRS Train Model

### 5.1 Detection

Identifies consecutive cars within 1.0s gap:
- Minimum train length: 3 cars
- Maximum train length: 8 cars
- Train dissolves when gap > 1.5s

### 5.2 Effects

| Role | DRS Effectiveness | Overtake Penalty | Dirty Air |
|------|-------------------|------------------|-----------|
| Leader | 0% (no DRS) | 0% | 1.0x (clean air) |
| Members | 70% (reduced) | -0.2 prob | 1.2x |

### 5.3 Practical Opportunity

Trains with >3 cars have reduced effective overtaking opportunity for members.

---

## 6. Defense Model

### 6.1 DefenseMode Thresholds

Based on relative_pace (attacker - defender, negative = attacker faster):

| Mode | Threshold | Pace Cost | Incident Risk |
|------|-----------|-----------|---------------|
| NORMAL | > 0.5 | 0.0 sec/lap | 1.0x |
| DEFENSIVE | 0.2 to 0.5 | 0.15 sec/lap | 1.3x |
| AGGRESSIVE | < 0.2 | 0.35 sec/lap | 2.0x |

Thresholds adjusted by:
- Defender skill: ±0.01 per point
- Pressure resistance: ±0.008 per point
- Aggression: ±0.005 per point
- Worn tyres (>70%): -0.3 aggressive threshold
- Track difficulty: ±0.2 per 0-1 difficulty
- Laps remaining < 10: +0.1 aggressive threshold

### 6.2 Line Choice

Probabilistic inside/outside choice based on:
- Corner type (inside favored for hairpin/slow)
- Defense mode (more inside for aggressive)
- Attacker overtaking skill
- Weather (more inside in wet)

---

## 7. Safety Car Restart Model

### 7.1 Field Compression

Under SC: all gaps compressed to ~0.5s ± 0.15s variance

### 7.2 Restart Evaluation

Per-driver reaction time (seconds):
```
base = 0.3s
- start_performance × 0.02
- pressure_resistance × 0.01
- consistency × 0.006
- aggression × 0.006
+ (80 - tyre_temp) × 0.005 (if < 80°C)
+ tyre_age × 0.02
+ weather effect
+ N(0, 0.15)
```

Clamped to [0.1, 1.0]s

### 7.3 Acceleration Advantage

Relative to field average:
```
(start_performance - 50) × 0.01
+ (tyre_temp - 90) × 0.01
- tyre_age × 0.04
+ (pressure_resistance - 50) × 0.005
+ N(0, 0.05)
```

Clamped to [-0.5, 0.5]

### 7.4 Position Change Probabilities

| Advantage | P(+1) | P(+2) | P(0) | P(-1) | P(-2) | P(-3) |
|-----------|-------|-------|------|-------|-------|-------|
| > 0.25 | 0.4-0.6 | 0.1-0.25 | rest | - | - | - |
| 0.1-0.25 | 0.3-0.4 | - | rest | - | - | - |
| -0.1 to 0.1 | - | - | 0.85 | 0.07 | 0.07 | - |
| < -0.1 | - | - | rest | 0.3-0.6 | 0.1-0.25 | - |
| < -0.25 | - | - | rest | 0.4-0.6 | 0.1-0.25 | 0.05 |

Leader cannot gain; backmarkers less likely to lose.

### 7.5 Incident Risk

Base: 2%
+ aggression × 0.0003
× 2.5 (wet), × 1.5 (damp)
× 1.5 (tyre temp < 70°C)
× 1.3 (tyre age > 25 laps)
× 1.2 (positions 5-15)
Capped at 15%

---

## 8. Incident Interaction

### 8.1 Battle Risk Modifiers

Battles increase base incident probability:
- Duration: +2% per lap
- Side-by-side: ×2.5
- Aggressive defense: ×2.0
- Defensive defense: ×1.3
- Attacker aggression: ×(1 + aggression/100 × 0.5)
- Defender aggression: ×(1 + aggression/100 × 0.3)
- Wet: ×1.5-2.0

### 8.2 Integration

IncidentModel remains the authority. Racing dynamics provide:
- `is_attacking`, `is_defending` flags
- Risk multipliers

Do NOT duplicate probability calculations.

---

## 9. Randomness & Determinism

All stochastic behavior uses named RandomProvider streams:

| Stream | Purpose |
|--------|---------|
| "overtaking" | Overtake opportunity & attempt |
| "battle" | Battle state transitions |
| "defense" | Line choice, mode selection |
| "restart" | Reaction time, acceleration, position change |
| "racing_incidents" | Battle-related incidents |

Same config + seed + model version → identical results.

---

## 10. Statistical Assumptions & Limitations

### 10.1 Assumptions

1. **Overtake probability** follows logistic curve from interpretable factors
2. **Dirty air** scales with inverse distance^1.5 (smooth, no discontinuities)
3. **Battles** persist across laps with state machine
4. **Defense** is reactive to pace delta, not predictive
5. **Safety car restart** uses reaction-time + acceleration model
6. **DRS train** reduces effectiveness but doesn't eliminate opportunity

### 10.2 Limitations

- No detailed vehicle physics (CFD, tire models, suspension)
- No collision geometry or wheel-to-wheel contact simulation
- Corner-type simplification (single type per evaluation)
- No fuel-strategy interaction during battles (separate model)
- No team orders or driver pairing logic
- Track-specific overtaking zones not modeled per-sector
- Safety car field compression is instantaneous (not lap-by-lap)

### 10.3 Calibration Targets

For future real-data calibration:
- Overtakes per race by track type
- Battle duration distributions
- DRS train formation frequency
- Safety car restart position changes
- Dirty air lap time delta by following distance

---

## 11. Configuration

All coefficients centralized in Pydantic config classes:

```python
OvertakeConfig()
BattleConfig()
DirtyAirConfig()
DRSTrainConfig()
DefenseConfig()
SafetyCarRestartConfig()
```

Add to `SimulationConfig` for track-specific overrides.

---

## 12. Future Improvements (Post-Phase 6)

1. **Sector-level dirty air**: Per-corner evaluation
2. **Predictive defense**: Anticipate attacker moves
3. **Fuel-aware battles**: ERS/fuel management during battles
4. **Team orders**: Multi-driver coordination
5. **Track-specific overtaking zones**: Per-sector probability maps
6. **ML-based calibration**: Historical data fitting
7. **Formation lap / standing start**: Phase 8+
8. **Red flag restarts**: Phase 8+
9. **Sprint weekends**: Phase 7+
10. **Championship context**: Phase 7+

---

## 13. Testing

### 13.1 Unit Tests (135 total, all passing)

- Overtake: gap thresholds, pace/tyre/DRS advantages, track difficulty, skills, weather
- Battle: creation, persistence, state transitions, side-by-side, termination
- DRS: availability, train detection, membership, dissolution
- Dirty Air: distance decay, corner types, aero sensitivity, smoothness
- Defense: mode selection, skill effects, line choice
- Safety Car Restart: field compression, deterministic restart, position preservation

### 13.2 Statistical Tests

Directional relationships verified with 1000+ samples:
- Pace advantage → higher overtake probability ✓
- Tyre delta → higher overtake probability ✓
- DRS enabled → higher overtake probability ✓
- Defending skill → lower overtake probability ✓
- Track difficulty → lower overtake probability ✓
- Aggressive driving → higher incident probability ✓
- Dirty air → lower following performance ✓

### 13.3 Integration Tests

Complete race scenarios:
- Two evenly matched drivers
- Fast attacker vs slow defender
- Strong DRS track (Bahrain)
- Difficult overtaking track (Monaco)
- Large DRS train (5+ cars)
- Safety car restart
- Wet race
- Aggressive battle

All verify: valid positions, no duplicate positions, no negative gaps, no corrupted state, events emitted, deterministic replay.

---

## 14. Performance

| Metric | Value |
|--------|-------|
| Races/second (5-lap, 2 cars) | 211 |
| Average race time | 4.7 ms |
| Memory | Stable, no leaks observed |

---

## 15. Files Added

```
app/simulation/racing/
├── __init__.py
├── models.py          # All contexts, decisions, configs, enums
├── overtake.py        # OvertakeEngine
├── battle.py          # BattleEngine, BattleState
├── dirty_air.py       # DirtyAirModel
├── drs_train.py       # DRSTrainModel
├── defense.py         # DefenseModel
├── safety_car_restart.py  # SafetyCarRestartModel
```

Extended:
- `app/simulation/core/events.py` - New event types
- `app/simulation/core/race_engine.py` - Integration