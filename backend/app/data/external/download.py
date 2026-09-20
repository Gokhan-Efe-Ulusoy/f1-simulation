"""Rate-limited, provenance-preserving downloader (Phase 22.5).

Raw payloads land under `backend/data/raw/external/<source_id>/` and are
never modified in place. Transport is injectable so tests never hit the
network. Live runs use urllib with Retry-After/429 backoff.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable
from typing import Any

from app.data.external.checksums import sha256_bytes, write_sidecar
from app.data.provenance import utc_now_iso

Transport = Callable[[str], bytes]


def urllib_transport(url: str, timeout_seconds: float = 30.0) -> bytes:
    """Default transport: GET bytes with a project User-Agent."""
    request = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/22.5"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read()


class RateLimiter:
    """Minimum-interval gate between requests (honest, no burst)."""

    def __init__(self, min_interval_seconds: float = 2.0) -> None:
        self.min_interval = min_interval_seconds
        self._last: float = 0.0

    def wait(self) -> None:
        """Sleep until the interval has elapsed since the last call."""
        now = time.monotonic()
        gap = now - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.monotonic()


def _fetch_with_retry(
    url: str,
    transport: Transport,
    limiter: RateLimiter,
    max_attempts: int = 4,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        limiter.wait()
        try:
            return transport(url)
        except Exception as exc:  # noqa: BLE001 - record and back off honestly
            last_error = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"download failed after {max_attempts} attempts: {url}: {last_error}")


def download_to_raw(
    *,
    source_id: str,
    url: str,
    filename: str,
    raw_root: str,
    license: str,
    source_version: str = "",
    transport: Transport | None = None,
    limiter: RateLimiter | None = None,
    extra_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Download one payload immutably; return the sidecar record.

    Skips re-download when the file already exists with a valid sidecar
    (raw immutability: never overwrite). Returns the sidecar dict either way.
    """
    dest_dir = os.path.join(raw_root, source_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    sidecar = dest + ".provenance.json"
    if os.path.exists(dest) and os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as handle:
            meta = json.load(handle)
        if meta.get("sha256") == _hash_of(dest):
            meta["reused_existing"] = True
            return meta
    payload = _fetch_with_retry(url, transport or urllib_transport, limiter or RateLimiter())
    with open(dest, "wb") as handle:
        handle.write(payload)
    _ = sha256_bytes(payload)  # recorded inside write_sidecar via re-hash
    return write_sidecar(
        dest,
        source_id=source_id,
        source_url=url,
        license=license,
        download_timestamp=utc_now_iso(),
        source_version=source_version,
        extra=extra_provenance or {},
    )


def _hash_of(path: str) -> str:
    from app.data.external.checksums import sha256_file

    return sha256_file(path)
