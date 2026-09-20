"""Phase 9B tests: adapters (fixture payloads only) and manifests."""
from __future__ import annotations

import json
import os

from app.data.manifests import run_ingestion
from app.data.sources.base import DataUnavailable
from app.data.sources.csv_adapter import OfficialCsvAdapter
from app.data.sources.fastf1_adapter import FastF1Adapter, fastf1_available
from app.data.sources.jolpica import JolpicaAdapter

SCHEDULE = {"MRData": {"RaceTable": {"Races": [
    {"season": "2024", "round": "1", "raceName": "Bahrain Grand Prix",
     "date": "2024-03-02", "Circuit": {"circuitId": "bahrain"}},
]}}}

RESULTS = {"MRData": {"RaceTable": {"Races": [
    {"season": "2024", "round": "1", "raceName": "Bahrain Grand Prix",
     "date": "2024-03-02", "Circuit": {"circuitId": "bahrain"},
     "Results": [
         {"position": "1", "points": "25",
          "Driver": {"driverId": "max_verstappen"},
          "Constructor": {"constructorId": "red_bull"},
          "grid": "1", "status": "Finished"},
         {"position": "2", "points": "18",
          "Driver": {"driverId": "perez"},
          "Constructor": {"constructorId": "red_bull"},
          "grid": "5", "status": "Finished"},
     ]},
]}}}


def _fake_transport(payload):
    def fetch(url: str):
        assert url.startswith("https://api.jolpi.ca/ergast/f1/")
        return payload
    return fetch


def test_jolpica_schedule_and_results() -> None:
    sched = JolpicaAdapter(transport=_fake_transport(SCHEDULE)).fetch_season(2024)
    assert len(sched.records) == 1
    assert sched.records[0]["raceName"] == "Bahrain Grand Prix"
    assert sched.rejected == []

    results = JolpicaAdapter(transport=_fake_transport(RESULTS)).fetch_race(2024, 1)
    assert len(results.records) == 2
    assert results.records[0]["Driver"]["driverId"] == "max_verstappen"
    assert results.records[0]["_season"] == 2024
    assert results.records[0]["_circuit_id"] == "bahrain"


def test_jolpica_malformed_shape_rejected_not_raised() -> None:
    bundle = JolpicaAdapter(transport=_fake_transport({"MRData": {}})).fetch_race(2024, 1)
    assert bundle.records == []
    assert bundle.rejected


def test_csv_adapter_valid_and_rejects() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "drivers.csv"), "w", encoding="utf-8") as handle:
            handle.write("driver_ref,full_name,nationality\n")
            handle.write("maxv,Max V,NLD\n")
            handle.write("\n")
            handle.write(",Nobody,\n")
        with open(os.path.join(tmp, "results.csv"), "w", encoding="utf-8") as handle:
            handle.write("season,round,driver_ref,position\n")
            handle.write("2024,1,maxv,1\n")
        adapter = OfficialCsvAdapter(tmp)
        drivers = adapter.fetch_driver("maxv")
        assert len(drivers.records) == 1
        assert adapter._read("drivers").rejected  # empty-key row rejected
        missing = adapter.fetch_constructor("x")
        assert missing.records == [] and missing.rejected  # absent file


def test_csv_missing_columns_rejected() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "results.csv"), "w", encoding="utf-8") as handle:
            handle.write("season,position\n2024,1\n")
        bundle = OfficialCsvAdapter(tmp).fetch_race(2024, 1)
        assert bundle.records == [] and bundle.rejected


def test_fastf1_architecture_without_backend() -> None:
    adapter = FastF1Adapter()
    assert adapter.is_available() == fastf1_available()
    if not fastf1_available():
        try:
            adapter.fetch_session(2024, "Bahrain", "R")
        except DataUnavailable:
            pass
        else:
            raise AssertionError("expected DataUnavailable")


def test_manifest_counts_and_files(tmp_path) -> None:
    sched = JolpicaAdapter(transport=_fake_transport(SCHEDULE)).fetch_season(2024)
    results = JolpicaAdapter(transport=_fake_transport(RESULTS)).fetch_race(2024, 1)
    manifest = run_ingestion(str(tmp_path), "jolpica", "2024/rounds 1",
                             [sched, results], run_id="run1")
    assert manifest.records_fetched == 3
    assert manifest.records_accepted == 3
    assert manifest.records_rejected == 0
    assert manifest.payload_hash
    assert os.path.exists(os.path.join(str(tmp_path), "data", "manifests", "run1.json"))
    assert os.path.exists(os.path.join(str(tmp_path), "data", "raw", "jolpica", "run1.json"))
    with open(os.path.join(str(tmp_path), "data", "raw", "jolpica", "run1.json"),
              encoding="utf-8") as handle:
        assert len(json.load(handle)) == 2
