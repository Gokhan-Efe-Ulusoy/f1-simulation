"""GitHub dataset/repository ingestion adapter (Phase 10E).

Supports raw CSV/JSON/Parquet, releases, pinned to commit SHA or tag.
Never executes downloaded code.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import urllib.request
from typing import Any

from app.data.provenance import make_provenance
from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter


def _sanitize_path(path: str) -> str:
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized) or normalized.startswith(".."):
        raise ValueError(f"unsafe path: {path}")
    if ".." in normalized.split(os.sep):
        raise ValueError(f"unsafe path: {path}")
    # Prevent formula injection in path components
    for part in normalized.split(os.sep):
        if part and part[0] in ("=", "+", "-", "@"):
            raise ValueError(f"unsafe path component: {part}")
    return normalized


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class GitHubSourceAdapter(SourceAdapter):
    """Adapter for GitHub repository datasets."""

    provider = "github"

    def __init__(self, base_dir: str = "data/raw/github") -> None:
        self.base_dir = base_dir

    def fetch_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,  # commit SHA or tag, pinned
        local_path: str | None = None,
    ) -> RawBundle:
        """Fetch a file from GitHub (local or remote).

        If local_path is provided, loads from local filesystem (offline).
        Otherwise fetches via raw.githubusercontent.com (requires network).
        Ref should be a commit SHA or tag for reproducibility.
        """
        if local_path:
            # Local mode (offline, test-friendly)
            # Validate repo-relative path even in local mode
            _sanitize_path(path)
            if not os.path.exists(local_path):
                raise DataUnavailable(f"GitHub local file not found: {local_path}")
            return self._load_local_file(local_path, owner, repo, path, ref)

        # Remote mode
        if not ref:
            raise DataUnavailable("GitHub fetch requires ref (commit SHA or tag) for provenance")
        safe_path = _sanitize_path(path)
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{safe_path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                content = resp.read()
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(str(exc)) from exc

        # Save to cache
        cache_dir = os.path.join(self.base_dir, _sanitize_path(owner),
                                 _sanitize_path(repo), _sanitize_path(ref))
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, os.path.basename(safe_path))
        with open(cache_path, "wb") as handle:
            handle.write(content)

        return self._parse_content(cache_path, content, owner, repo, safe_path, ref)

    def _load_local_file(self, local_path: str, owner: str, repo: str,
                         path: str, ref: str | None) -> RawBundle:
        with open(local_path, "rb") as handle:
            content = handle.read()
        return self._parse_content(local_path, content, owner, repo, path, ref)

    def _parse_content(self, fpath: str, content: bytes, owner: str, repo: str,
                       path: str, ref: str | None) -> RawBundle:
        ext = os.path.splitext(fpath)[1].lower()
        file_hash = hashlib.sha256(content).hexdigest()
        records: list[dict[str, Any]] = []

        if ext == ".csv":
            text = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(text.splitlines())
            for row in reader:
                clean_row = {}
                for k, v in row.items():
                    if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@"):
                        v = "'" + v
                    clean_row[k] = v
                clean_row["_source"] = f"github:{owner}/{repo}"
                clean_row["_path"] = path
                if ref:
                    clean_row["_ref"] = ref
                clean_row["_file_hash"] = file_hash
                records.append(clean_row)
        elif ext == ".json":
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        item["_file_hash"] = file_hash
                        records.append(item)
            elif isinstance(data, dict):
                data["_file_hash"] = file_hash
                records.append(data)
        else:
            return RawBundle(provider=self.provider,
                             endpoint=f"github:{owner}/{repo}/{path}",
                             rejected=[f"unsupported extension: {ext}"])

        provenance = make_provenance(
            source_provider=self.provider,
            source_record_id=f"{owner}/{repo}/{path}@{ref or 'local'}",
            source_url=f"https://github.com/{owner}/{repo}/blob/{ref or 'main'}/{path}",
            raw_payload=records[:3],
            steps=["fetch_file"],
        )

        return RawBundle(
            provider=self.provider,
            endpoint=f"github:{owner}/{repo}/{path}@{ref or 'local'}",
            records=records,
            warnings=[f"provenance: {provenance.raw_file_hash[:8]}"] if records else [],
        )

    def fetch_season(self, season: int) -> RawBundle:
        raise DataUnavailable("GitHub adapter requires explicit repo/path via fetch_file")

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        raise DataUnavailable("GitHub adapter requires explicit repo/path via fetch_file")
