# Security Policy

## Reporting a vulnerability

Email the project owner with `[SECURITY]` in the subject, including: affected
revision, reproduction steps, and impact assessment. Do not open a public
issue for unpatched vulnerabilities. Expect acknowledgement within 7 days.
There is no bug-bounty program.

## Secret handling (repository rules — enforced)

- **Never commit** `.env`, API keys, tokens, passwords, credentials, private
  keys, certificates, or database credentials. `.env` / `.env.*` are
  git-ignored; only `*.env.example` templates (placeholders, no real values)
  are tracked. Phase 33 audit: **no secrets found in the tree**.
- The Postgres credentials in `docker-compose.yml`
  (`postgres:postgres`) and the defaults in `backend/.env.example` /
  `app/core/settings.py` are **local-development defaults only**. Override
  them via environment for anything beyond localhost:
  `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`.
- If a secret is ever committed: rotate it immediately, report it, and do
  **not** rewrite published history without owner approval (history surgery
  is a separate, announced operation).

## Dependency security

- Backend pins live in `backend/pyproject.toml`; frontend lockfile
  `frontend/package-lock.json` is committed and CI installs with `npm ci`.
- No dependency upgrades in Phase 33; upgrade PRs must keep the test suite
  green and note behaviour risk.
- Optional dependencies (FastF1) are import-guarded and never required.

## API / data-source handling

- All API input is Pydantic-validated; path traversal and future-field
  injection are rejected and covered by tests (`test_path_traversal*`,
  leakage suite).
- External data providers (Jolpica, OpenF1, Open-Meteo, f1db, FastF1) are
  untrusted input: payloads are checksummed (`.sha256` sidecars) and
  quarantined on mismatch, never silently merged. Provider terms are listed
  in `backend/data/licensing.json`.
- Simulation results must never be presented as official timing data.

## Disclosure

Fixes are released with a CHANGELOG entry describing impact without
exploit details. Contributors touching auth, secrets, or provenance must
call it out in the PR description (see `CONTRIBUTING.md`).
