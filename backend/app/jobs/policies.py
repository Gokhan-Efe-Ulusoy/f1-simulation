"""Phase 30 — Policies: limits, retries, concurrency."""

from __future__ import annotations

# Resource limits (conservative defaults)
MAX_SYNC_MONTE_CARLO = 1000
MAX_ASYNC_MONTE_CARLO = 5000  # public API limit preserved; internal chunked supports up to 100000
MAX_CHUNKED_TOTAL = 100000
DEFAULT_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 5000
MIN_CHUNK_SIZE = 1
MAX_CONCURRENT_JOBS = 4
MAX_JOB_RUNTIME_SECONDS = 300
MAX_RETRIES = 2  # total attempts = max_attempts = 2 (initial + 1 retry)
MAX_QUEUE_DEPTH = 100

# Priority: bounded int 0..100. LOW=10, NORMAL=50, HIGH=90.
PRIORITY_LOW = 10
PRIORITY_NORMAL = 50
PRIORITY_HIGH = 90
PRIORITY_MIN = 0
PRIORITY_MAX = 100

# Valid status transitions (Phase 31 adds TIMEOUT)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"RUNNING", "CANCELLED", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED", "QUEUED", "TIMEOUT"},  # QUEUED for retry
    "COMPLETED": set(),
    "FAILED": {"QUEUED"},  # retry only via new attempt
    "CANCELLED": set(),
    "TIMEOUT": {"QUEUED"},  # retry allowed
}

RETRYABLE_ERRORS = {
    "transient worker error",
    "temporary database",
    "temporary queue",
    "worker crash",
    "heartbeat expired",
    "stale job",
}

NON_RETRYABLE_SUBSTRINGS = (
    "validation error",
    "leakage",
    "invalid",
    "unsupported",
    "unknown",
    "malformed",
    "deterministic",
    "scientific",
)


def is_retryable_error(msg: str) -> bool:
    low = msg.lower()
    if any(s in low for s in NON_RETRYABLE_SUBSTRINGS):
        return False
    return any(s in low for s in RETRYABLE_ERRORS) or "transient" in low


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, set())
