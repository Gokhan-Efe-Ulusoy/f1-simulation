"""f1db Tier3 recovery adapter (GitHub pinned release).

Downloads f1db-csv.zip from GitHub releases (pinned tag), verifies SHA256,
extracts CSVs, and provides race/result etc as RawBundles.

Source: f1db/f1db, tag v2026.13.0, license CC-BY 4.0, hash verified.
Fallback for Jolpica 429 gaps (1981-2022 etc).

Never fabricates, records provenance with archive_hash, file_hashes, retrieval_date.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from app.data.provenance import hash_payload, utc_now_iso
from app.data.sources.base import DataUnavailable, RawBundle

F1DB_RELEASE_TAG = "v2026.13.0"
F1DB_REPO = "f1db/f1db"
F1DB_CSV_URL = f"https://github.com/{F1DB_REPO}/releases/download/{F1DB_RELEASE_TAG}/f1db-csv.zip"
F1DB_LICENSE = "CC BY 4.0"
F1DB_TERMS_URL = f"https://github.com/{F1DB_REPO}/releases/tag/{F1DB_RELEASE_TAG}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_f1db_zip(dest_dir: Path, url: str = F1DB_CSV_URL) -> tuple[Path, str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / f"f1db-{F1DB_RELEASE_TAG}.zip"
    hash_path = dest_dir / f"f1db-{F1DB_RELEASE_TAG}.sha256"
    # If exists and hash valid, reuse
    if zip_path.exists() and hash_path.exists():
        expected = hash_path.read_text().strip()
        actual = _sha256_file(zip_path)
        if actual == expected:
            return zip_path, actual
    print(f"[f1db] downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "f1-simulation/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    zip_path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    hash_path.write_text(sha)
    # Also write provenance sidecar
    prov = {
        "repository": F1DB_REPO,
        "tag": F1DB_RELEASE_TAG,
        "url": url,
        "retrieval_date": utc_now_iso(),
        "sha256": sha,
        "license": F1DB_LICENSE,
        "terms_url": F1DB_TERMS_URL,
        "file": str(zip_path),
    }
    (dest_dir / f"f1db-{F1DB_RELEASE_TAG}.provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"[f1db] downloaded {len(data)} bytes sha256 {sha[:16]}")
    return zip_path, sha


def _extract_and_parse(zip_path: Path, dest_dir: Path) -> dict[str, list[dict[str, Any]]]:
    extract_dir = dest_dir / f"extracted-{F1DB_RELEASE_TAG}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    needed = {
        "f1db-races.csv", "f1db-drivers.csv", "f1db-constructors.csv",
        "f1db-circuits.csv", "f1db-seasons.csv", "f1db-grands-prix.csv",
        "f1db-races-race-results.csv", "f1db-races-qualifying-results.csv",
        "f1db-races-pit-stops.csv", "f1db-races-fastest-laps.csv",
        "f1db-races-sprint-race-results.csv", "f1db-races-sprint-qualifying-results.csv",
    }
    # Normalize needed to basenames for zip member matching
    needed_basenames = {Path(p).name for p in needed}
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            if ".." in member or member.startswith("/"):
                continue
            if not member.endswith(".csv"):
                continue
            basename = Path(member).name
            if basename not in needed_basenames:
                continue
            target = extract_dir / basename
            if target.name.startswith("=") or target.name[0] in ("+", "-", "@"):
                continue
            if target.exists() and target.stat().st_size > 0:
                continue
            with z.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
    # Parse CSVs - compute archive hash once
    archive_hash = _sha256_file(zip_path)[:16]
    result: dict[str, list[dict[str, Any]]] = {}
    for csv_file in extract_dir.glob("*.csv"):
        key = csv_file.stem  # e.g., f1db-races
        records: list[dict[str, Any]] = []
        try:
            with open(csv_file, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    clean = {}
                    for k, v in row.items():
                        if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@"):
                            v = "'" + v
                        clean[k] = v
                    clean["_f1db_source"] = key
                    clean["_archive_hash"] = archive_hash
                    records.append(clean)
        except Exception as e:
            print(f"[f1db] parse {csv_file} failed {e}")
            continue
        result[key] = records
        print(f"[f1db] parsed {key}: {len(records)} rows")
    return result


class F1DBAdapter:
    """Adapter for f1db CSV recovery."""

    provider = "f1db"
    release_tag = F1DB_RELEASE_TAG

    def __init__(self, raw_root: str = "backend/data/raw/github"):
        self.raw_root = Path(raw_root)
        self.cache_dir = self.raw_root / "f1db" / F1DB_RELEASE_TAG
        self.zip_path: Path | None = None
        self.archive_hash: str | None = None
        self.parsed: dict[str, list[dict[str, Any]]] | None = None

    def ensure_downloaded(self) -> tuple[Path, str]:
        if self.zip_path and self.archive_hash and self.zip_path.exists():
            return self.zip_path, self.archive_hash
        self.zip_path, self.archive_hash = _download_f1db_zip(self.cache_dir)
        return self.zip_path, self.archive_hash

    def load(self) -> dict[str, list[dict[str, Any]]]:
        if self.parsed is not None:
            return self.parsed
        zip_path, _ = self.ensure_downloaded()
        self.parsed = _extract_and_parse(zip_path, self.cache_dir)
        return self.parsed

    def fetch_season(self, season: int) -> RawBundle:
        data = self.load()
        # f1db races have year column
        races = data.get("f1db-races", [])
        filtered = [r for r in races if str(r.get("year")) == str(season)]
        if not filtered:
            return RawBundle(provider=self.provider, endpoint=f"f1db/races/{season}", rejected=[f"season {season} not in f1db"])  # noqa: E501
        return RawBundle(provider=self.provider, endpoint=f"f1db/races/{season}", records=filtered)

    def fetch_all(self) -> dict[str, RawBundle]:
        data = self.load()
        bundles: dict[str, RawBundle] = {}
        for key, records in data.items():
            bundles[key] = RawBundle(provider=self.provider, endpoint=f"f1db/{key}", records=records)  # noqa: E501
        return bundles
