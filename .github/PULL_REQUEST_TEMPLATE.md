# Pull Request template — please complete all sections.

## What / why

## Scientific impact (required if simulation behaviour may change)

- [ ] No simulation mathematics changed
- [ ] Rationale + evidence attached (or N/A)
- [ ] Reproducibility impact stated (seeds, fingerprints, versions)
- [ ] Limitations updated (`NON_IDENTIFIABLE` / `NOT_AVAILABLE` where applicable)

If behaviour changed: link benchmarks before/after (same seed, same dataset,
`PYTHONHASHSEED=0`) and the version bump per `docs/version_lineage.md`.

## Verification

- [ ] `git status` clean; no secrets, caches, build output, backups, `>100 MB` files
- [ ] Backend unit suite green (`backend-unit` CI job)
- [ ] API suite green where local dataset present (or note skip + why)
- [ ] Frontend `npm test -- --ci` + `npm run build` green
- [ ] `python backend/scripts/verify_dataset.py` (full or `--offline`) green
- [ ] No new `ruff`/`mypy` issues introduced

## Data / provenance

- [ ] No raw/canonical data committed; manifests append-only
- [ ] New inputs carry evidence tiers; missing data is `null` + availability record
