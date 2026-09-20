"""Phase 9A tests: canonical schemas, provenance, availability, versions."""
from __future__ import annotations

import pytest

from app.data.availability import COVERAGE_TIERS, availability_for, has_coverage
from app.data.models.canonical import (
    DataProvenance,
    DataQualityReport,
    HistoricalDriver,
    HistoricalRace,
    HistoricalResult,
)
from app.data.provenance import hash_payload, make_provenance
from app.data.versions import DatasetVersion, list_versions, register_version


def test_stable_ids_and_aliases() -> None:
    driver = HistoricalDriver(driver_id="driver:colt", full_name="Colt",
                              aliases=["C. Olt"])
    assert driver.driver_id == "driver:colt"
    assert "C. Olt" in driver.aliases


def test_missing_data_is_null_not_fabricated() -> None:
    result = HistoricalResult(result_id="r", race_id="race:x", driver_id="driver:y")
    assert result.final_position is None
    assert result.total_time_seconds is None
    assert result.grid_position is None


def test_units_encoded_in_field_names() -> None:
    fields = set(HistoricalResult.model_fields)
    assert "total_time_seconds" in fields
    assert "time_gap_seconds" in fields
    assert "time" not in fields
    assert "speed" not in fields


def test_entity_event_separation() -> None:
    race = HistoricalRace(race_id="1994-san-marino", season_id="1994",
                          round=3, circuit_id="circuit:imola")
    assert race.race_id != race.circuit_id
    assert race.season_id == "1994"


def test_provenance_chain_and_hash_stability() -> None:
    payload = {"a": 1, "b": [2, 3]}
    assert hash_payload(payload) == hash_payload({"b": [2, 3], "a": 1})
    assert hash_payload(payload) != hash_payload({"a": 2})
    prov = make_provenance("jolpica", source_record_id="r1", raw_payload=payload,
                           steps=["fetch"])
    assert prov.parser_version and prov.retrieved_at and prov.raw_file_hash
    assert prov.confidence == 1.0
    extended = prov.extended("normalize")
    assert extended.transformation_chain == ["fetch", "normalize"]
    assert prov.transformation_chain == ["fetch"]  # original untouched


def test_provenance_model_allows_empty() -> None:
    prov = DataProvenance(source_provider="manual")
    assert prov.transformation_chain == []


def test_availability_tiers() -> None:
    assert set(COVERAGE_TIERS) >= {"race_results", "telemetry", "sectors"}
    assert not has_coverage("telemetry", 1960)
    assert has_coverage("race_results", 1960)
    assert has_coverage("telemetry", 2024)
    rec = availability_for("telemetry", 1960, source="jolpica")
    assert rec.available is False
    assert rec.coverage_start == 2020
    unknown = availability_for("telepathy", 2024)
    assert unknown.available is False


def test_dataset_version_immutable_and_registry_append_only(tmp_path) -> None:
    from pydantic import ValidationError

    version = DatasetVersion(dataset_id="f1-dataset-v0.1.0")
    with pytest.raises(ValidationError):
        version.dataset_id = "mutated"  # type: ignore[misc]
    register_version(str(tmp_path), version)
    with pytest.raises(ValueError):
        register_version(str(tmp_path), version)  # duplicate rejected
    listed = list_versions(str(tmp_path))
    assert [v.dataset_id for v in listed] == ["f1-dataset-v0.1.0"]
    assert listed[0].schema_version


def test_quality_report_clean_flag() -> None:
    assert DataQualityReport(dataset_version="v").is_clean
    assert not DataQualityReport(dataset_version="v", errors=["x"]).is_clean
