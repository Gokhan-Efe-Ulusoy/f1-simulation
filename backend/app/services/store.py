"""Phase 29 — Persistent simulation store (DB + in-memory fallback)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

try:
    from app.core.database import SessionLocal, init_db
    from app.models.simulation import SimulationRecord

    init_db()
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    SessionLocal = None  # type: ignore[assignment]
    SimulationRecord = None  # type: ignore[assignment]

from app.services.hashing import result_hash  # noqa: E402


class SimulationStore:
    """Persistent store with DB primary, in-memory fallback. No Redis."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._max = max_entries
        self.db_available = DB_AVAILABLE

    def _persist_db(
        self,
        payload: dict[str, Any],
        status: str,
        simulation_type: str,
        race_id: str,
        seed: int | None,
        sample_count: int | None,
        request_hash: str | None,
        execution_time: float | None,
    ) -> None:
        if not self.db_available or SessionLocal is None:
            return
        try:
            sid = payload.get("simulation_id")
            res_hash = result_hash(payload)
            # extract versions from provenance if present
            prov = payload.get("provenance") or payload.get("execution_metadata") or {}
            # handle nested provenance
            if isinstance(prov, dict) and "provenance" in payload:
                prov = payload.get("provenance", {})
            engine_ver = payload.get("model_versions", {}).get("race_engine_version") or prov.get("race_engine_version") or "raceengine-v2.2.0"  # noqa: E501
            model_ver = payload.get("model_versions", {}).get("model_version") or prov.get("model_version") or "0.9.0"  # noqa: E501
            dataset_ver = prov.get("dataset_version") or "f1-dataset-v1.3"
            dataset_hash = prov.get("dataset_hash") or "sha256:canonical-races-v1.3"
            fingerprint = payload.get("provenance_fingerprint") or payload.get("fingerprint") or prov.get("fingerprint") or request_hash  # noqa: E501
            # need to handle session
            session = SessionLocal()
            try:
                # upsert
                existing = session.get(SimulationRecord, sid) if sid else None
                if existing:
                    existing.status = status
                    existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)  # noqa: E501
                    existing.result = json.dumps(payload, default=str)
                    existing.result_hash = res_hash
                    existing.execution_time = execution_time
                    existing.request_hash = request_hash or existing.request_hash
                else:
                    rec = SimulationRecord(
                        simulation_id=sid,
                        status=status,
                        simulation_type=simulation_type,
                        race_id=race_id or payload.get("race_id", "unknown"),
                        seed=seed,
                        sample_count=sample_count,
                        request_hash=request_hash,
                        result_hash=res_hash,
                        engine_version=str(engine_ver),
                        model_version=str(model_ver),
                        dataset_version=str(dataset_ver),
                        dataset_hash=str(dataset_hash),
                        provenance_fingerprint=str(fingerprint or ""),
                        execution_time=execution_time,
                        result=json.dumps(payload, default=str),
                    )
                    session.add(rec)
                session.commit()
            finally:
                session.close()
        except Exception:
            # fallback to memory only on DB failure
            pass

    def create(self, payload: dict[str, Any], status: str = "completed") -> str:
        sid = payload.get("simulation_id") or f"sim_{uuid.uuid4().hex[:12]}"
        payload["simulation_id"] = sid
        payload["status"] = status
        payload["created_at"] = payload.get("created_at") or time.time()
        # infer fields for DB
        simulation_type = payload.get("type") or payload.get("simulation_type") or "unknown"
        # normalize type
        if simulation_type == "race":
            simulation_type = "race"
        elif simulation_type in ("monte_carlo", "montecarlo", "mc"):
            simulation_type = "monte_carlo"
        race_id = payload.get("race_id") or "unknown"
        seed = payload.get("seed")
        sample_count = payload.get("simulations") or payload.get("N") or payload.get("sample_count")
        request_hash = payload.get("request_hash") or (payload.get("execution_metadata") or {}).get("request_hash") if isinstance(payload.get("execution_metadata"), dict) else None  # noqa: E501
        execution_time = payload.get("runtime", {}).get("elapsed_seconds") if isinstance(payload.get("runtime"), dict) else None  # noqa: E501
        if execution_time is None:
            execution_time = (payload.get("execution_metadata") or {}).get("execution_time") if isinstance(payload.get("execution_metadata"), dict) else None  # noqa: E501

        # persist to DB
        self._persist_db(payload, status, simulation_type, race_id, seed, sample_count, request_hash, execution_time)  # noqa: E501

        # also keep in memory for fast fallback
        if len(self._data) >= self._max:
            oldest = min(self._data, key=lambda k: self._data[k].get("created_at", 0))
            self._data.pop(oldest, None)
        self._data[sid] = payload
        return sid

    def create_with_lifecycle(
        self,
        payload: dict[str, Any],
        simulation_type: str,
        race_id: str,
        seed: int | None,
        sample_count: int | None,
        request_hash: str | None,
    ) -> str:
        """Create with explicit lifecycle: QUEUED -> RUNNING -> COMPLETED/FAILED, persisted."""
        sid = payload.get("simulation_id") or f"sim_{uuid.uuid4().hex[:12]}"
        payload["simulation_id"] = sid
        # start as QUEUED then RUNNING for sync execution
        payload["status"] = "QUEUED"
        payload["created_at"] = time.time()
        payload["simulation_type"] = simulation_type
        # persist QUEUED
        self._persist_db(payload, "QUEUED", simulation_type, race_id, seed, sample_count, request_hash, None)  # noqa: E501
        # self._data also
        self._data[sid] = dict(payload)
        # transition to RUNNING
        payload["status"] = "RUNNING"
        self._persist_db(payload, "RUNNING", simulation_type, race_id, seed, sample_count, request_hash, None)  # noqa: E501
        self._data[sid] = dict(payload)
        return sid

    def complete(self, sid: str, payload: dict[str, Any], execution_time: float | None = None) -> None:  # noqa: E501
        payload["status"] = "COMPLETED"
        payload["updated_at"] = time.time()
        if execution_time is not None:
            payload["execution_time"] = execution_time
        self._persist_db(
            payload,
            "COMPLETED",
            payload.get("simulation_type", "unknown"),
            payload.get("race_id", "unknown"),
            payload.get("seed"),
            payload.get("simulations") or payload.get("N"),
            payload.get("request_hash") or (payload.get("execution_metadata") or {}).get("request_hash") if isinstance(payload.get("execution_metadata"), dict) else None,  # noqa: E501
            execution_time,
        )
        self._data[sid] = payload

    def fail(self, sid: str, error: str, simulation_type: str = "unknown", race_id: str = "unknown") -> None:  # noqa: E501
        payload = self._data.get(sid, {"simulation_id": sid})
        payload["status"] = "FAILED"
        payload["error"] = error
        payload["updated_at"] = time.time()
        self._persist_db(payload, "FAILED", simulation_type, race_id, payload.get("seed"), None, None, None)  # noqa: E501
        self._data[sid] = payload

    def get(self, sid: str) -> dict[str, Any] | None:
        # try DB first
        if self.db_available and SessionLocal is not None:
            try:
                session = SessionLocal()
                try:
                    rec = session.get(SimulationRecord, sid)
                    if rec:
                        d = rec.to_dict()
                        # result is stored as JSON string
                        if d.get("result"):
                            # result field contains full payload
                            try:
                                payload = d["result"] if isinstance(d["result"], dict) else json.loads(d["result"]) if isinstance(d["result"], str) else d["result"]  # noqa: E501
                                if isinstance(payload, dict):
                                    # ensure status reflects record status
                                    payload["status"] = d["status"]
                                    payload["created_at"] = d["created_at"]
                                    payload["updated_at"] = d["updated_at"]
                                    return payload
                            except Exception:
                                pass
                        # fallback to record dict
                        return d
                finally:
                    session.close()
            except Exception:
                pass
        return self._data.get(sid)

    def set_status(self, sid: str, status: str, result: dict[str, Any] | None = None) -> None:
        if sid in self._data:
            self._data[sid]["status"] = status
            if result is not None:
                self._data[sid]["result"] = result
        # also persist
        if self.db_available and SessionLocal is not None:
            try:
                session = SessionLocal()
                try:
                    rec = session.get(SimulationRecord, sid)
                    if rec:
                        rec.status = status
                        if result is not None:
                            rec.result = json.dumps(result, default=str)
                        import datetime

                        rec.updated_at = datetime.datetime.now(datetime.UTC)
                        session.commit()
                finally:
                    session.close()
            except Exception:
                pass


store = SimulationStore()
