# F1 Simulation Platform

A professional-grade Formula 1 simulation platform with modular architecture, deterministic modeling, and Monte Carlo capabilities.

## Overview

This project implements a scientifically grounded Formula 1 simulation engine capable of simulating:
- Individual laps with physics-based lap time models
- Qualifying sessions (Q1, Q2, Q3)
- Full races with pit stops, tyre degradation, fuel effects
- Weather changes and safety car periods
- Overtaking, incidents, and mechanical failures
- Championship seasons with points standings
- Monte Carlo simulations for probability analysis

## Architecture

```
f1-simulation/
├── backend/           # FastAPI backend with simulation engine
│   └── app/
│       ├── api/       # REST API endpoints
│       ├── core/      # Configuration and settings
│       ├── domain/    # Domain models (Driver, Car, Track, etc.)
│       ├── simulation/# Simulation engine (RaceEngine, StrategyEngine, etc.)
│       ├── models/    # Database models
│       ├── services/  # Business logic services
│       ├── repositories/ # Data access layer
│       ├── data/      # Static data (tracks, teams, drivers)
│       ├── schemas/   # Pydantic schemas for API
│       └── utils/     # Utilities
├── frontend/          # Next.js React frontend
│   └── app/           # App Router pages
│       ├── components/# Reusable UI components
│       ├── features/  # Feature-specific components
│       ├── lib/       # Utility functions
│       ├── hooks/     # Custom React hooks
│       └── types/     # TypeScript types
├── simulation/        # Standalone simulation engine (no HTTP/DB dependencies)
└── docs/              # Documentation
```

## Technology Stack

### Backend
- Python 3.12+
- FastAPI
- Pydantic v2
- NumPy, SciPy, Pandas
- SQLAlchemy 2.0 + PostgreSQL
- pytest, ruff, mypy, pre-commit

### Frontend
- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- Recharts for visualizations
- shadcn/ui component library

### Development
- Docker & Docker Compose
- Git
- Ruff (linting/formatting)
- MyPy (type checking)
- Pre-commit hooks

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for local development)
- Node.js 20+ (for local development)

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

### Local Development

#### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Development Commands

### Backend
```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Lint and format
ruff check . --fix
ruff format .

# Type check
mypy app/

# Run pre-commit hooks
pre-commit run --all-files
```

### Frontend
```bash
# Run development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint

# Type check
npm run type-check

# Run tests
npm test
```

## Project Phases

This project follows a structured 16-phase development process:

- **Phase 0**: Architecture and repository setup ✓
- **Phase 1**: Domain models and configuration
- **Phase 2**: Driver + Car + Track + Lap-time model
- **Phase 3**: Single-lap simulation
- **Phase 4**: Full race engine
- **Phase 5**: Tyres + Fuel + Pit stops
- **Phase 6**: Strategy engine
- **Phase 7**: Weather
- **Phase 8**: Overtaking + Incidents + Safety Car
- **Phase 9**: Qualifying + Championship
- **Phase 10**: Monte Carlo
- **Phase 11**: Historical calibration
- **Phase 12**: FastAPI endpoints
- **Phase 13**: Next.js frontend
- **Phase 14**: Live race visualization
- **Phase 15**: Performance optimization
- **Phase 16**: Advanced simulation models

## Core Principles

1. **Modular architecture** - Separation of concerns
2. **Deterministic simulations** - Reproducible results with seeds
3. **Strong typing** - Pydantic models throughout
4. **Configuration-driven** - No magic numbers
5. **Scientifically defensible** - Every component has a reason
6. **Extensive testing** - Unit, integration, and validation tests
7. **Documentation** - All assumptions documented

## API Endpoints (Planned)

```
POST   /api/v1/simulations/race        # Simulate a single race
POST   /api/v1/simulations/season      # Simulate a championship season
POST   /api/v1/simulations/monte-carlo # Run Monte Carlo simulations
GET    /api/v1/drivers                 # List drivers
GET    /api/v1/teams                   # List teams
GET    /api/v1/tracks                  # List tracks
GET    /api/v1/championships           # List championships
GET    /api/v1/health                  # Health check
```

## Frontend Pages (Planned)

1. **Home** - Dashboard overview
2. **Race Simulator** - Configure and run race simulations
3. **Live Race** - Real-time race visualization
4. **Driver Profiles** - Driver statistics and performance
5. **Team Profiles** - Team and car performance
6. **Track Profiles** - Circuit characteristics
7. **Strategy** - Pit stop and tyre strategy optimization
8. **Championship** - Season simulation and standings
9. **Monte Carlo** - Probability analysis
10. **Custom Scenario** - Alternate history scenarios

## License

MIT License - see LICENSE file for details.