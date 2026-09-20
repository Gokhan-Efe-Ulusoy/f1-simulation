"""Kaggle dataset ingestion adapter (Phase 10E - pinned, provenance-aware)."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from typing import Any

from app.data.provenance import make_provenance
from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter


def _sanitize_path(path: str) -> str:
    """Prevent path traversal."""
    # Normalize and reject absolute or traversal
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized) or normalized.startswith(".."):
        raise ValueError(f"unsafe path: {path}")
    if ".." in normalized.split(os.sep):
        raise ValueError(f"unsafe path: {path}")
    return normalized


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class KaggleSourceAdapter(SourceAdapter):
    """Adapter for curated Kaggle datasets (owner/slug, versioned)."""

    provider = "kaggle"

    def __init__(self, base_dir: str = "data/raw/kaggle") -> None:
        self.base_dir = base_dir

    def _dataset_dir(self, owner: str, dataset: str) -> str:
        return os.path.join(self.base_dir, _sanitize_path(owner), _sanitize_path(dataset))

    def fetch_dataset(
        self,
        owner: str,
        dataset: str,
        version: str | None = None,
        file_name: str | None = None,
    ) -> RawBundle:
        """Load a locally downloaded Kaggle dataset (offline-first).

        Expects files under base_dir/owner/dataset/. Records dataset
        provenance including hashes.
        """
        dataset_dir = self._dataset_dir(owner, dataset)
        if not os.path.exists(dataset_dir):
            raise DataUnavailable(f"Kaggle dataset not found locally: {owner}/{dataset}")

        # Find files
        files = []
        for root, _, filenames in os.walk(dataset_dir):
            for fname in filenames:
                if file_name and fname != file_name:
                    continue
                # Sanitize and avoid formula injection
                if fname.startswith("=") or fname.startswith("+"):
                    continue
                files.append(os.path.join(root, fname))

        if not files:
            return RawBundle(provider=self.provider,
                             endpoint=f"kaggle/{owner}/{dataset}",
                             rejected=["no files found"])

        records: list[dict[str, Any]] = []
        for fpath in sorted(files):
            # Validate extension
            ext = os.path.splitext(fpath)[1].lower()
            if ext not in (".csv", ".json"):
                continue
            file_hash = _file_hash(fpath)
            if ext == ".csv":
                with open(fpath, newline="", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        # Sanitize formula injection in values
                        clean_row = {}
                        for k, v in row.items():
                            if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@"):
                                v = "'" + v
                            clean_row[k] = v
                        clean_row["_source_file"] = os.path.basename(fpath)
                        clean_row["_file_hash"] = file_hash
                        clean_row["_dataset"] = f"{owner}/{dataset}"
                        if version:
                            clean_row["_version"] = version
                        records.append(clean_row)
            elif ext == ".json":
                with open(fpath, encoding="utf-8") as handle:
                    data = json.load(handle)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                item["_source_file"] = os.path.basename(fpath)
                                item["_file_hash"] = file_hash
                                records.append(item)
                    elif isinstance(data, dict):
                        data["_source_file"] = os.path.basename(fpath)
                        data["_file_hash"] = file_hash
                        records.append(data)

        provenance = make_provenance(
            source_provider=self.provider,
            source_record_id=f"{owner}/{dataset}",
            source_url=f"https://www.kaggle.com/datasets/{owner}/{dataset}",
            raw_payload=records[:5],  # hash sample
            steps=["fetch_dataset"],
        )

        return RawBundle(
            provider=self.provider,
            endpoint=f"kaggle/{owner}/{dataset}",
            records=records,
            warnings=[f"provenance: {provenance.raw_file_hash[:8]}"] if records else [],
        )

    # SourceAdapter interface compliance
    def fetch_season(self, season: int) -> RawBundle:
        raise DataUnavailable("Kaggle adapter requires explicit dataset via fetch_dataset")

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        raise DataUnavailable("Kaggle adapter requires explicit dataset via fetch_dataset")
