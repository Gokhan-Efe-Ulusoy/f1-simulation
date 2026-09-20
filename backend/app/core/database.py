"""Phase 29 — Database engine / Base / init."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/f1sim")  # noqa: E501

# Fallback to SQLite file if postgres not available or driver missing
# Use sync engine for store (sync FastAPI). If DATABASE_URL is asyncpg, try sync fallback.
SYNC_URL = DATABASE_URL
if "+asyncpg" in SYNC_URL:
    # try psycopg2 if installed, else fallback to sqlite
    try:
        import importlib.util

        if importlib.util.find_spec("psycopg2") is not None:
            SYNC_URL = SYNC_URL.replace("+asyncpg", "+psycopg2")
        else:
            raise ImportError
    except Exception:
        SYNC_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'data' / 'simulations.db'}"
        Path(SYNC_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
elif SYNC_URL.startswith("sqlite"):
    Path(SYNC_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
else:
    # ensure directory for default sqlite
    try:
        Path(__file__).resolve().parents[2] / "data"
        Path(SYNC_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# Default to sqlite file if postgres sync driver not available
try:
    engine = create_engine(SYNC_URL, echo=False, future=True)
    # test connection quickly
    with engine.connect() as _conn:
        pass
except Exception:
    sqlite_path = Path(__file__).resolve().parents[2] / "data" / "simulations.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    SYNC_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(SYNC_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """Create tables if not exist + lightweight migration for new columns."""
    try:
        # import models to register
        import app.jobs.models  # noqa: F401  # type: ignore[import]
        import app.models.simulation  # noqa: F401  # type: ignore[import]

        Base.metadata.create_all(bind=engine)
        # SQLite: add missing columns idempotently
        try:
            from sqlalchemy import inspect, text

            insp = inspect(engine)
            if "jobs" in insp.get_table_names():
                cols = {c["name"] for c in insp.get_columns("jobs")}
                adds = {
                    "timed_out_at": "TIMESTAMP",
                    "chunk_size": "INTEGER",
                    "chunk_count": "INTEGER",
                    "completed_chunks": "INTEGER",
                    "total_chunks": "INTEGER",
                }
                with engine.begin() as conn:
                    for col, typ in adds.items():
                        if col not in cols:
                            conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col} {typ}"))
        except Exception:
            pass
    except Exception:
        pass
