# Phase 32 — Product Architecture

```
USER → Next.js Frontend → API Client → FastAPI REST API → Execution Service
→ (Simulation Service → RaceEngine | Job Queue → Worker/Jobs) → Simulation Store → Result/Replay
```

- Frontend never calculates outcomes; backend owns data (`backend/data/**` never imported by Next.js).
- No Redux/Zustand/React Query: native `useState/useEffect`, `fetch` via centralized `app/lib/api/` (client, races, simulations, scenarios, types). Base URL `NEXT_PUBLIC_API_URL` (fallback localhost:8000/api/v1).
- Polling `GET /simulation/{id}` every 2s, stops on COMPLETED/FAILED/CANCELLED/TIMEOUT; stage-level progress only, never fabricated per-lap %.
- Shell: `app/layout.tsx` nav (/, /simulator, /monte-carlo, /strategy, /championship). `/simulator` is the functional page; others are honest entry points (Monte Carlo links to simulator; Strategy/Championship show planned-disabled status).
