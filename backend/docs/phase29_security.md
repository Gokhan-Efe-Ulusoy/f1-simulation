# Phase 29 — Security

Preserves all Phase 28 guarantees.

- CORS: `app/main.py` `CORSMiddleware` with `settings.CORS_ORIGINS` (localhost:3000,8000).
- Request size: Pydantic `max_length 100` for race_id, `simulations 1-5000`, `laps 1-200`, interventions 20, `track_pit_loss 0-60`, events capped 200.
- Path traversal: `..`, `/`, `\` rejected in every `race_id`, `simulation_id`, `checkpoint` (see `schemas.py` validators + endpoint guards). `GET /simulation/../../etc/passwd` → 422/404 (tested `test_security_path_traversal_simulation`).
- No filesystem paths from client: server resolves canonical root internally (`race_service._canonical_root()`), never trusts client path.
- No arbitrary code: no `eval`, `exec`, `subprocess`, dynamic imports from user input, no `open` with user path.
- Scenario allowlists: `registry.FAMILY_OPS/PARAMS` + `validation.validate_spec` enforce allowlist; leakage blocklist (`future_*`, `observed_result`, `actual_`, `realized`, `final_position`, `championship`, `standing`) still enforced (tested `test_leakage_*`).
- Error handling: structured `ErrorCode`, `RequestValidationError` handler returns `{"error": {"code": "VALIDATION_ERROR", ...}}` without stack traces; `StarletteHTTPException` similarly sanitized.
- Persistence: `GET /simulation/{id}` checks traversal, returns 404 `DATA_NOT_AVAILABLE` for unknown IDs (tested `test_unknown_simulation_id`), does not leak DB credentials/paths.
- New: persisted-result access tested (`test_persistent_storage`), request hashing excludes transient data.

Residual: CORS `allow_methods=["*"]` permissive; consider restricting to GET/POST in production. In-memory fallback still present but DB primary where available.
