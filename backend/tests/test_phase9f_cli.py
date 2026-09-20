"""Phase 9F tests: coverage report, CLI, reproducibility."""
from __future__ import annotations

import json
import os

from app.data.__main__ import main
from app.data.coverage import build_coverage_report, render_text


def test_coverage_report_machine_and_human_readable() -> None:
    report = build_coverage_report(1950, 2026)
    assert set(report["summary"]) >= {"race_results", "telemetry"}
    assert report["summary"]["telemetry"]["first_season"] == 2020
    assert report["summary"]["race_results"]["first_season"] == 1950
    text = render_text(report)
    assert "1950" in text and "2026" in text


def test_cli_coverage_writes_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    os.makedirs("data/validation", exist_ok=True)
    assert main(["coverage"]) == 0
    with open("data/validation/coverage.json", encoding="utf-8") as handle:
        assert "summary" in json.load(handle)


def test_cli_validate_clean_and_dirty(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    canonical = os.path.join("canon")
    os.makedirs(canonical)
    good = {
        "races": [{"race_id": "r1", "date": "2024-03-02", "scheduled_laps": 57,
                   "circuit_id": "c1"}],
        "results": [{"result_id": "r1:d1", "race_id": "r1", "driver_id": "d1",
                     "constructor_id": "c1", "final_position": 1}],
        "drivers": [{"driver_id": "d1"}],
        "constructors": [{"constructor_id": "c1"}],
    }
    for name, rows in good.items():
        with open(os.path.join(canonical, f"{name}.json"), "w", encoding="utf-8") as handle:
            json.dump(rows, handle)
    assert main(["validate", "--canonical-dir", canonical, "--dataset", "v1"]) == 0
    with open(os.path.join(canonical, "results.json"), "w", encoding="utf-8") as handle:
        json.dump([{"result_id": "r1:d1", "race_id": "r1", "driver_id": "d1",
                    "final_position": 99}], handle)
    assert main(["validate", "--canonical-dir", canonical, "--dataset", "v1"]) == 1


def test_cli_conflicts_and_features_and_calibration(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with open("facts.json", "w", encoding="utf-8") as handle:
        json.dump({"facts": [["r1", "winner", {"a": "X", "b": "X"}],
                             ["r2", "winner", {"a": "X", "b": "Y"}]]}, handle)
    assert main(["conflicts", "--facts", "facts.json"]) == 0
    results = [{"race_id": "s:r1", "driver_id": "d1", "constructor_id": "c1",
                "grid_position": 2, "final_position": 1, "status": "finished"}]
    with open("results.json", "w", encoding="utf-8") as handle:
        json.dump(results, handle)
    assert main(["build-features", "--season", "2024", "--results", "results.json",
                 "--out", "features.json"]) == 0
    with open("features.json", encoding="utf-8") as handle:
        assert len(json.load(handle)) > 0
    assert main(["build-calibration", "--features", "features.json",
                 "--out", "calibration.json"]) == 0
    with open("calibration.json", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["method"] == "identity-baseline"
    assert payload["profile"]["profile_id"] == "identity-baseline"


def test_cli_csv_ingest_offline(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    os.makedirs("csvin", exist_ok=True)
    with open("csvin/races.csv", "w", encoding="utf-8") as handle:
        handle.write("season,round,race_name,circuit_ref\n2024,1,Bahrain,bahrain\n")
    with open("csvin/results.csv", "w", encoding="utf-8") as handle:
        handle.write("season,round,driver_ref,position\n2024,1,maxv,1\n")
    assert main(["ingest", "--source", "csv", "--csv-dir", "csvin",
                 "--season", "2024", "--round", "1"]) == 0
    assert os.path.exists("data/manifests")


def test_pipeline_reproducibility() -> None:
    from app.data.normalization import normalize_jolpica_result
    from app.data.provenance import hash_payload
    from app.data.resolution import AliasRegistry

    row = {"_season": 2024, "_round": 1, "_race_name": "Bahrain GP",
           "_circuit_id": "bahrain", "_date": "2024-03-02",
           "Driver": {"driverId": "max_verstappen"},
           "Constructor": {"constructorId": "red_bull"},
           "grid": "1", "position": "1", "status": "Finished", "points": "25"}
    first = normalize_jolpica_result(row)
    second = normalize_jolpica_result(dict(row))
    assert first == second
    assert hash_payload(first[0]) == hash_payload(second[0])
    for _ in range(2):
        registry = AliasRegistry()
        registry.register_entity("c:mclaren", ["McLaren", "McLaren F1 Team"])
        assert registry.resolve("MCLAREN F1 TEAM") == "c:mclaren"
