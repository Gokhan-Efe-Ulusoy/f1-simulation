"""Rate limiting and retry logic for network adapters (Phase 10B)."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class RateLimiter:
    """Token-bucket rate limiter with retry, exponential backoff, Retry-After, jitter."""

    def __init__(
        self,
        requests_per_second: float = 0.5,
        timeout_seconds: float = 30.0,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.requests_per_second = requests_per_second
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self._last_request: float = 0.0

    def wait_if_needed(self) -> None:
        """Sleep if needed to respect rate limit."""
        if self.requests_per_second <= 0:
            return
        min_interval = 1.0 / self.requests_per_second
        elapsed = time.time() - self._last_request
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request = time.time()

    def _retry_delay_for(self, exc: Exception, attempt: int, base: float) -> float:
        """Honor Retry-After for 429, add jitter."""
        import random

        msg = str(exc)
        # Parse Retry-After if present (urllib HTTPError may contain headers)
        retry_after = None
        if hasattr(exc, "headers"):
            try:
                retry_after = exc.headers.get("Retry-After")  # type: ignore
            except Exception:
                pass
        if retry_after is not None:
            try:
                return float(retry_after) + (random.uniform(0, 1) if self.jitter else 0)
            except ValueError:
                pass
        # 429 gets longer base
        if "429" in msg:
            base = max(base, 10.0)  # at least 10s for 429
        jitter = random.uniform(0, 0.5 * base) if self.jitter else 0
        return base + jitter

    def execute_with_retry(self, func: Callable[[], Any]) -> Any:
        """Execute func with retry and exponential backoff, honoring 429."""
        import random

        last_exc: Exception | None = None
        delay = self.backoff_base
        for attempt in range(self.max_retries + 1):
            try:
                self.wait_if_needed()
                return func()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == self.max_retries:
                    break
                sleep = self._retry_delay_for(exc, attempt, delay)
                time.sleep(sleep)
                delay *= self.backoff_multiplier
                # Temporary cooldown for persistent 429
                if "429" in str(exc) and attempt >= 2:
                    time.sleep(15.0 + random.uniform(0, 5))
        raise last_exc  # type: ignore[misc]
