"""Phase 30 — Cancellation tokens (cooperative)."""

from __future__ import annotations

import threading

_tokens: dict[str, bool] = {}
_lock = threading.Lock()


def request_cancellation(job_id: str) -> None:
    with _lock:
        _tokens[job_id] = True


def is_cancelled(job_id: str) -> bool:
    with _lock:
        return _tokens.get(job_id, False)


def clear_cancellation(job_id: str) -> None:
    with _lock:
        _tokens.pop(job_id, None)
