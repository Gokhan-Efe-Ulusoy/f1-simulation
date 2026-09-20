# Phase 29 — Persistence

## Backend

SQLAlchemy 2.0 + PostgreSQL (production) with SQLite fallback (`data/simulations.db`) for CI/local without Docker. Dependencies already in `pyproject.toml` (`sqlalchemy>=2.0`, `asyncpg`).

- `app/core/database.py`: sync `create_engine(SYNC_URL)`, `SessionLocal`, `Base`, `init_db()`. Tries `DATABASE_URL` (postgresql+asyncpg → postgresql+psycopg2 if driver present), else `sqlite:///data/simulations.db`. Creates directory, tests connection, falls back to sqlite on failure.
- `app/models/simulation.py`: `SimulationRecord` table.

## Schema

Table `simulations` (PK `simulation_id` String(128)):
```
simulation_id PK, indexed
created_at DateTime(timezone=True), indexed, default now
updated_at DateTime, onupdate now
status String(32) indexed: QUEUED|RUNNING|COMPLETED|FAILED
simulation_type String(32) indexed: race, monte_carlo, scenario, replay, strategy
race_id String(128) indexed
seed Integer nullable
sample_count Integer nullable (N)
request_hash String(64) indexed
result_hash String(64)
engine_version String(64)
model_version String(64)
dataset_version String(64)
dataset_hash String(64)
provenance_fingerprint String(64)
execution_time Float nullable
error Text nullable (JSON string if failed)
result Text nullable (JSON string, JSONB on postgres)
```
Indexes: `ix_simulations_race_created (race_id, created_at)`, `ix_simulations_type_status`.

## Store

`app/services/store.py:SimulationStore` — DB primary, in-memory fallback (`dict[str,dict]` max 1000 LRU).

- `create(payload, status)`: generates `sim_{uuid hex12}` if no id, sets `created_at`, infers `simulation_type`, `race_id`, `seed`, `sample_count`, `request_hash`, `execution_time` from payload, persists via `_persist_db` (upsert), also caches in `_data`.
- `create_with_lifecycle(...)`: creates QUEUED→RUNNING for sync execution.
- `complete(sid, payload, execution_time)`: updates to COMPLETED, persists result JSON.
- `fail(sid, error, ...)`: sets FAILED, persists error.
- `get(sid)`: tries DB `session.get(SimulationRecord, sid)` first, parses `result` JSON, returns payload with status; falls back to `_data`.
- `set_status(sid, status, result)`: updates both.

Result payload may be stored as JSON string; `to_dict()` handles.

## Lifecycle

```
QUEUED → RUNNING → COMPLETED
              ↘ FAILED
```
Phase29: synchronous execution does QUEUED→RUNNING in `POST` handler, then engine run (blocking), then COMPLETED/FAILED. No Celery/Redis; scaffolded statuses allow future worker queue upgrade.

## Persistence Guarantees

- `POST /simulate/race` with `save_replay=true` (default) persists COMPLETED result; `GET /simulation/{id}` retrieves persisted (DB or memory) — verified `test_persistent_storage`, `test_serialization_round_trip`.
- Serialize→persist→retrieve preserves result within JSON tolerance (floats/ints, no numpy).
- No duplication of canonical dataset into DB; no raw external source files stored.
- Simulation IDs collision-safe via `uuid4`; deterministic content via `request_hash`/`result_hash` (not same ID).

## Upgrade Path

Future: replace sync `create_engine` with async `create_async_engine` + `async_session`, add `BackgroundTasks` or `arq` worker polling `QUEUED`. Table already supports.
