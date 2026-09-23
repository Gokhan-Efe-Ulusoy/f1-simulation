# Contributing

## Setup

```bash
# Backend (Python 3.12)
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (.venv/bin/activate on POSIX)
pip install -e ".[dev]"
cp .env.example .env
$env:PYTHONHASHSEED = "0"       # required for cross-process reproducibility

# Frontend (Node 20)
cd frontend
npm ci
```

Run: data-free unit tests → `verify_dataset.py --offline` → (with a local
dataset) the phase suites → `npm test` + `npm run build`. Full test map:
`README.md` "Testing" + `backend/docs/phase33_repository_audit.md`.

## Branch / PR workflow

- Branch from `master`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
- Keep PRs small and logically separated (audit / CI / config / docs /
  packaging — never one giant commit).
- CI must be green: backend unit (gates), API suite where data is present,
  frontend tests + build. Note in the PR if the API suite was skipped for
  lack of local data.
- `git status` clean; no `.env`, caches, build output, backups, or
  `>100 MB` files. Check `git diff --cached --stat` before committing.

## Coding standards

- Python: `ruff check` + `ruff format`, line length 100; type hints on new
  public functions (mypy has pre-existing errors — don't add new ones).
- TypeScript: `npm run lint`, `tsc --noEmit`, prettier.
- No hardcoded secrets, tokens, or machine-specific absolute paths.
  No new dependency without a `docs/dependencies.md` entry.

## Scientific integrity requirements (non-negotiable)

**You cannot simply tune coefficients until the simulation looks
realistic.** Any change affecting simulation behaviour must include, in the
PR:

1. **Rationale** — what evidence motivates the change.
2. **Evidence** — data sources, tier changes (`PRIOR_ONLY` → `LIMITED` →
   `CALIBRATED` only via the promotion-gate process; never automatic).
3. **Tests** — determinism preserved, leakage suite green, regression pins
   updated deliberately (legacy `race_engine_v*` tests pin history —
   touching them needs explicit justification).
4. **Reproducibility** — seed behaviour, fingerprint impact, and
   `PYTHONHASHSEED` sensitivity stated.
5. **Version impact** — model/engine/simulation bump per
   `docs/version_lineage.md`.
6. **Limitations** — what remains `NON_IDENTIFIABLE` / `NOT_AVAILABLE`
   after your change. Never replace a limitation with an assumption.

Prohibited: fabricated data, invented calibration coefficients, silent
promotion of `PRIOR_ONLY` / `LIMITED` / `NON_IDENTIFIABLE` parameters,
fake endpoints, weakened assertions to make tests pass, deleting
functionality without a deprecation note.

## Data provenance requirements

- Raw/canonical data is never committed; manifests are append-only.
- New data handling must write `.sha256` + `.provenance.json` sidecars and
  validate via `scripts/verify_dataset.py` (which never repairs).
- Missing data is `null` + an availability record — never invented.
