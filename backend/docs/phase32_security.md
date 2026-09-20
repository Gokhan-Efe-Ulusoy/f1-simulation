# Phase 32 — Security

- Frontend adds no new attack surface: no eval, no filesystem paths, URLs built only from `encodeURIComponent(raceId/simulationId)` + fixed base URL; backend validation remains authoritative (client-side checks duplicated, never trusted).
- Backend unchanged: leakage blocklist, Pydantic limits, path-traversal guards, sanitized errors all preserved and covered by contract tests (leakage 422, oversized N 422, traversal 404/422).
