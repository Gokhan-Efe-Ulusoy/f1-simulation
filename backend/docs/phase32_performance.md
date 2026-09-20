# Phase 32 — Performance

- Frontend: `next build` First Load JS ~87–94 kB per route (simulator 6.18 kB page + 93.1 kB first load); no new dependencies (fetch, native hooks). No premature optimization.
- API: no regression — Phase 32 made zero backend source changes; determinism spot-check and contract suite timings unchanged (contract suite ~3–19s cached). Result rendering is plain tables (no recharts on simulator path).
