# Architecture Documentation

## System Overview

The F1 Simulation Platform is a modular, layered architecture designed for:
- Deterministic, reproducible simulations
- Separation of simulation logic from infrastructure
- Extensibility for future simulation models
- High performance for Monte Carlo runs

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Pages   │ │Components│ │  Hooks   │ │   Visualization │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└──────────────────────────┬────────────────────────────────────┘
                           │ HTTP/REST API
┌──────────────────────────▼────────────────────────────────────┐
│                    Backend API (FastAPI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Routes  │ │ Schemas  │ │ Services │ │  Repositories  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└──────────────────────────┬────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│              Simulation Engine (Standalone)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ RaceEng  │ │StrategyE │ │MonteCarlo│ │   Domain Models │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ LapTimeM │ │ TyreMod  │ │FuelModel │ │  OvertakeMod   │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │WeatherMod│ │IncidentM │ │ SafetyCar│ │  PitStopModel  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

## Core Design Principles

### 1. Separation of Concerns
- **Simulation Engine**: Pure Python, no HTTP, no DB, no framework dependencies
- **API Layer**: Thin FastAPI wrapper around simulation engine
- **Frontend**: Pure React/Next.js, communicates only via REST API
- **Data Layer**: SQLAlchemy models separate from domain models

### 2. Deterministic Simulations
- All randomness controlled by a single `seed` parameter
- Centralized `RandomProvider` abstraction
- Same config + same seed = identical results
- Model version recorded in every simulation result

### 3. Domain-Driven Design
- Explicit domain models for all core entities
- No untyped dictionaries for core objects
- Pydantic models for validation and serialization
- Clear boundaries between domain and infrastructure

### 4. Configuration-Driven
- All simulation parameters externalized
- YAML/JSON configuration files
- Environment-specific overrides
- No magic numbers in code

## Key Components

### Simulation Engine (`simulation/`)

The standalone simulation engine is the heart of the system:

```
simulation/
├── models/           # Domain models (Driver, Car, Track, Tyre, etc.)
├── core/             # Core simulation primitives
│   ├── random.py     # RandomProvider abstraction
│   ├── state.py      # SimulationState, RaceState
│   ├── events.py     # Event system (LapStarted, PitStopCompleted, etc.)
│   └── config.py     # SimulationConfig
├── lap_time/         # Lap time calculation models
├── tyre/             # Tyre compound and degradation models
├── fuel/             # Fuel mass and burn rate models
├── overtake/         # Overtaking probability models
├── pit/              # Pit stop time models
├── strategy/         # Strategy optimization engine
├── weather/          # Weather evolution models
├── incident/         # Incident probability models
├── safety_car/       # Safety car / VSC models
├── qualifying/       # Qualifying simulation
├── championship/     # Championship engine
└── monte_carlo/      # Monte Carlo runner
```

### Domain Models

All domain models use Pydantic for validation:

```python
# Example: Driver model
class Driver(BaseModel):
    id: str
    name: str
    team_id: str
    # Skills (0-100 scale)
    overall_skill: float
    qualifying_skill: float
    race_skill: float
    consistency: float
    aggression: float
    tyre_management: float
    wet_weather_skill: float
    overtaking: float
    defending: float
    start_performance: float
    adaptability: float
    pressure_resistance: float
    mistake_rate: float
```

### Random Number Abstraction

```python
# simulation/core/random.py
class RandomProvider:
    def __init__(self, seed: int):
        self._rng = np.random.default_rng(seed)
    
    def random(self) -> float: ...
    def normal(self, mean: float, std: float) -> float: ...
    def choice(self, seq, p=None): ...
    def integers(self, low: int, high: int): ...
```

### Event System

Structured events for frontend visualization:

```python
# simulation/core/events.py
class SimulationEvent(BaseModel):
    event_type: str
    timestamp: float
    lap: int
    data: dict

class LapStarted(SimulationEvent): ...
class PitStopStarted(SimulationEvent): ...
class OvertakeCompleted(SimulationEvent): ...
class IncidentOccurred(SimulationEvent): ...
class SafetyCarDeployed(SimulationEvent): ...
class RaceFinished(SimulationEvent): ...
```

## Data Flow

### Race Simulation Flow

```
1. SimulationConfig (seed, track, drivers, cars, weather, strategy)
         │
         ▼
2. RaceEngine.initialize() → SimulationState
         │
         ▼
3. For each lap:
   a. Calculate driver/car performance
   b. Update tyre degradation
   c. Update fuel mass
   d. Process overtaking opportunities
   e. Check for incidents
   f. Process pit stops
   g. Handle safety car / VSC
   h. Calculate lap times
   i. Update positions
   j. Emit events
         │
         ▼
4. RaceEngine.finalize() → RaceResult
         │
         ▼
5. Store result / Return via API
```

### Monte Carlo Flow

```
1. MonteCarloConfig (base_config, num_simulations, output_metrics)
         │
         ▼
2. For i in range(num_simulations):
   a. Derive seed = base_seed + i
   b. Run single simulation
   c. Collect metrics
         │
         ▼
3. Aggregate results → MonteCarloResult
   - Win probabilities
   - Podium probabilities
   - Average positions
   - DNF rates
   - Confidence intervals
```

## API Design

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/simulations/race` | Single race simulation |
| POST | `/api/v1/simulations/season` | Championship season |
| POST | `/api/v1/simulations/monte-carlo` | Monte Carlo analysis |
| GET | `/api/v1/drivers` | List all drivers |
| GET | `/api/v1/teams` | List all teams |
| GET | `/api/v1/tracks` | List all tracks |
| GET | `/api/v1/championships` | List championships |

### Request/Response Models

All API models use Pydantic schemas in `app/schemas/`.

Example race simulation request:
```json
{
  "track_id": "monaco",
  "seed": 12345,
  "weather": "dry",
  "laps": 78,
  "drivers": [...],
  "strategy_overrides": {}
}
```

Example response:
```json
{
  "race_id": "uuid",
  "seed": 12345,
  "model_version": "0.1.0",
  "results": [
    {"position": 1, "driver_id": "VER", "total_time": "1:30:45.123", "pit_stops": 2, ...}
  ],
  "events": [...],
  "fastest_lap": {"driver_id": "VER", "time": "1:12.345", "lap": 42}
}
```

## Frontend Architecture

### State Management
- React Context for global state (theme, user preferences)
- TanStack Query for server state (simulation results, driver data)
- Local component state for UI interactions

### Page Structure
```
app/
├── page.tsx                 # Home dashboard
├── simulator/page.tsx       # Race configuration & results
├── live/[raceId]/page.tsx   # Live race view (WebSocket)
├── championship/page.tsx    # Season simulation
├── monte-carlo/page.tsx     # Monte Carlo configuration & results
├── strategy/page.tsx        # Strategy optimization
├── drivers/[id]/page.tsx    # Driver profile
├── teams/[id]/page.tsx      # Team profile
├── tracks/[id]/page.tsx     # Track profile
└── custom/page.tsx          # Custom scenarios
```

### Visualization Components
- Leaderboard table with gaps, tyres, pit stops
- Lap time charts (Recharts)
- Tyre strategy timeline
- Track map with car positions (SVG/Canvas)
- Probability distributions (Monte Carlo)

## Database Schema (Planned)

```sql
-- Core tables
drivers (id, name, team_id, skills_json, ...)
teams (id, name, car_specs_json, ...)
tracks (id, name, country, length_km, sectors_json, ...)
tyres (id, compound, performance, degradation, ...)

-- Simulation results
races (id, track_id, seed, model_version, config_json, started_at, finished_at)
race_results (race_id, driver_id, position, total_time, laps, pit_stops, dnf_reason)
lap_times (race_id, driver_id, lap, time, tyre_compound, tyre_age, fuel_mass, ...)
events (race_id, lap, event_type, event_data_json)

-- Championship
championships (id, name, year, calendar_json)
championship_standings (championship_id, driver_id, points, wins, podiums, ...)
```

## Testing Strategy

### Unit Tests
- Each model component tested in isolation
- Deterministic tests with fixed seeds
- Property-based tests for mathematical models

### Integration Tests
- Full race simulation
- Championship season
- Monte Carlo aggregation

### Validation Tests
- Statistical sanity checks (faster car → better results)
- Historical calibration against real data
- Regression tests for model changes

## Performance Considerations

### Current (Phase 0)
- No optimization needed
- Focus on correctness

### Future Optimizations
- Vectorized NumPy operations for Monte Carlo
- Multiprocessing for parallel simulations
- Caching for repeated configurations
- Optional GPU acceleration for large batches
- Database connection pooling

## Deployment

### Docker Compose (Development)
```yaml
services:
  postgres:    # PostgreSQL 16
  backend:     # FastAPI + Uvicorn
  frontend:    # Next.js dev server
```

### Production (Planned)
- Backend: Gunicorn + Uvicorn workers
- Frontend: Next.js standalone build
- Database: PostgreSQL with read replicas
- Load balancer: Nginx/Traefik
- Monitoring: Prometheus + Grafana
- Logging: Structured JSON logs

## Extensibility Points

1. **New Tyre Models**: Implement `TyreModel` protocol
2. **New Lap Time Models**: Implement `LapTimeModel` protocol
3. **New Weather Models**: Implement `WeatherModel` protocol
4. **New Strategy Algorithms**: Implement `StrategyOptimizer` protocol
5. **New Incident Types**: Extend `IncidentModel`
6. **Custom Domain Models**: Add to `simulation/models/`

## Versioning

- Simulation model versioned separately from API version
- Each simulation result records: seed, model_version, config
- Breaking changes to simulation require model version bump
- API versioned in URL path (`/api/v1/`)

## Security

- No authentication in Phase 0 (add in Phase 12+)
- CORS configured for frontend origin only
- Input validation via Pydantic schemas
- Rate limiting on API endpoints (future)
- SQL injection prevention via SQLAlchemy ORM