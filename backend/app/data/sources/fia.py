"""FIA / Official documents adapter architecture (Phase 10 - curated import).

Stores document identifier, publication date, version, URL, hash,
extracted fields and extraction method. No OCR attempted in Phase 10.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from app.data.provenance import make_provenance
from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter


class FiaDocumentAdapter(SourceAdapter):
    """Adapter for curated FIA/official document imports."""

    provider = "fia"

    def __init__(self, base_dir: str = "data/raw/fia") -> None:
        self.base_dir = base_dir

    def import_document(
        self,
        document_id: str,
        file_path: str,
        publication_date: str = "",
        version: str = "1.0",
        url: str = "",
        extracted_fields: dict[str, Any] | None = None,
    ) -> RawBundle:
        """Import a curated document (local file, offline)."""
        if not os.path.exists(file_path):
            raise DataUnavailable(f"FIA document not found: {file_path}")

        with open(file_path, "rb") as handle:
            content = handle.read()
        file_hash = hashlib.sha256(content).hexdigest()

        # Try to parse as JSON, fallback to raw
        try:
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, dict):
                record = dict(data)
            else:
                record = {"content": data}
        except (json.JSONDecodeError, UnicodeDecodeError):
            record = {"raw_size": len(content)}

        record.update({
            "_document_id": document_id,
            "_publication_date": publication_date,
            "_version": version,
            "_url": url,
            "_file_hash": file_hash,
            "_extracted_fields": extracted_fields or {},
        })

        provenance = make_provenance(
            source_provider=self.provider,
            source_record_id=document_id,
            source_url=url,
            raw_payload=record,
            steps=["import_document"],
        )

        return RawBundle(
            provider=self.provider,
            endpoint=f"fia/{document_id}",
            records=[record],
            warnings=[f"provenance: {provenance.raw_file_hash[:8]}"],
        )

    def fetch_season(self, season: int) -> RawBundle:
        raise DataUnavailable("FIA adapter is document-oriented, use import_document")

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        raise DataUnavailable("FIA adapter is document-oriented, use import_document")
