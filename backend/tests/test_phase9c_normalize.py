"""Phase 9C tests: normalization, entity resolution, validation, conflicts."""
from __future__ import annotations

from app.data.conflicts import compare_fact, detect_conflicts
from app.data.normalization import (
    normalize_compound,
    normalize_csv_result,
    normalize_date,
    normalize_duration_seconds,
    normalize_int,
    normalize_jolpica_result,
    normalize_session,
)
from app.data.resolution import AliasRegistry, make_race_id, make_result_id, normalize_name
from app.data.validation import validate_bundle


def test_duration_parsing_and_ambiguity() -> None:
    assert normalize_duration_seconds("1:32:03.456") == 5523.456
    assert normalize_duration_seconds("1:23.456") == 83.456
    assert normalize_duration_seconds("+12.345") == 12.345
    assert normalize_duration_seconds("83.456") == 83.456
    for bad in ("", "-", "N/A", "abc", "1:2:3:4", "-5"):
        assert normalize_duration_seconds(bad) is None
    assert normalize_duration_seconds(None) is None


def test_date_compound_session_int_normalization() -> None:
    assert normalize_date("2024-03-02") == "2024-03-02"
    assert normalize_date("02/03/2024") == "2024-03-02"
    assert normalize_date("not a date") is None
    assert normalize_compound("Soft") == "soft"
    assert normalize_compound("I") == "intermediate"
    assert normalize_compound("ultrasoft") is None
    assert normalize_session("R") == "race"
    assert normalize_session("Sprint Shootout") == "sprint_qualifying"
    assert normalize_int("5") == 5
    assert normalize_int("5.5") is None
    assert normalize_int("") is None


def test_jolpica_row_mapping_and_warnings() -> None:
    row = {"_season": 2024, "_round": 1, "_race_name": "Bahrain GP",
           "_circuit_id": "bahrain", "_date": "2024-03-02",
           "Driver": {"driverId": "max_verstappen"},
           "Constructor": {"constructorId": "red_bull"},
           "grid": "1", "position": "1", "status": "Finished", "points": "25",
           "FastestLap": {"Time": {"time": "1:32.608"}, "lap": "39"},
           "Time": {"time": "1:31:44.742"}}
    record, warnings = normalize_jolpica_result(row)
    assert warnings == []
    assert record["season"] == 2024 and record["round"] == 1
    assert record["date"] == "2024-03-02"
    assert record["points"] == 25.0
    assert record["fastest_lap"] == 92.608
    assert record["total_time_seconds"] == 5504.742
    bad, warnings = normalize_jolpica_result({"Driver": {}, "points": "lots"})
    assert bad["driver_ref"] == ""
    assert any("driver_ref" in w for w in warnings)
    assert any("points" in w for w in warnings)


def test_csv_row_mapping_flags_bad_ints() -> None:
    record, warnings = normalize_csv_result(
        {"season": "2024", "round": "x", "driver_ref": "d", "grid": "pole"})
    assert record["season"] == 2024
    assert record["round"] is None
    assert any("round" in w for w in warnings)
    assert any("grid" in w for w in warnings)


def test_entity_resolution_aliases_and_accents() -> None:
    registry = AliasRegistry()
    registry.register_entity("constructor:mclaren",
                             ["McLaren", "McLaren F1 Team", "McLaren International"])
    assert registry.resolve("mclaren f1 team") == "constructor:mclaren"
    assert registry.resolve("MCLAREN") == "constructor:mclaren"
    assert registry.resolve("Ferrari") is None
    assert registry.aliases_for("constructor:mclaren") == sorted(
        registry.aliases_for("constructor:mclaren"))
    other = AliasRegistry()
    other.register_entity("driver:raikkonen", ["Kimi Räikkönen"])
    assert other.resolve("kimi raikkonen") == "driver:raikkonen"


def test_alias_conflict_rejected() -> None:
    registry = AliasRegistry()
    registry.register_entity("constructor:a", ["Alpha"])
    try:
        registry.register_entity("constructor:b", ["alpha"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected alias conflict")


def test_event_identity_separate_from_circuit() -> None:
    san_marino = make_race_id(1994, "San Marino Grand Prix")
    emilia = make_race_id(2020, "Emilia-Romagna Grand Prix")
    assert san_marino != emilia
    assert make_result_id(san_marino, "driver:senna") != make_result_id(emilia, "driver:senna")
    assert normalize_name("San Marino GP") == "san marino"


def test_validation_catches_listed_problems() -> None:
    report = validate_bundle(
        "v",
        races=[{"race_id": "r1", "date": "not-a-date", "scheduled_laps": 500,
                "circuit_id": ""},
               {"race_id": "r1", "date": "2024-03-02"}],
        results=[
            {"result_id": "x", "race_id": "missing", "driver_id": "ghost",
             "final_position": 99, "grid_position": 0,
             "total_time_seconds": -1.0, "laps_completed": -2, "points": 25.0},
            {"result_id": "y", "race_id": "r1", "driver_id": "ghost",
             "final_position": 1, "points": 18.0},
            {"result_id": "z", "race_id": "r1", "driver_id": "ghost",
             "final_position": 2, "points": 25.0},
        ],
        drivers=[{"driver_id": "someone-else"}],
        constructors=[],
    )
    assert not report.is_clean
    joined = "\n".join(report.errors)
    for needle in ("duplicate race: r1", "impossible date", "impossible lap count",
                   "orphaned race", "orphaned driver", "invalid final_position",
                   "invalid grid_position", "negative total_time_seconds",
                   "negative laps", "inconsistent points"):
        assert needle in joined, needle
    assert report.statistics == {"races": 2, "results": 3, "drivers": 1, "constructors": 0}


def test_validation_clean_bundle() -> None:
    report = validate_bundle(
        "v",
        races=[{"race_id": "r1", "date": "2024-03-02", "scheduled_laps": 57,
                "circuit_id": "c1"}],
        results=[{"result_id": "r1:d1", "race_id": "r1", "driver_id": "d1",
                  "constructor_id": "c1", "final_position": 1, "grid_position": 1,
                  "total_time_seconds": 5000.0, "laps_completed": 57, "points": 25.0}],
        drivers=[{"driver_id": "d1"}],
        constructors=[{"constructor_id": "c1"}],
    )
    assert report.is_clean


def test_conflicts_agreement_none_disagreement_recorded() -> None:
    assert compare_fact("r1", "winner", {"a": "X", "b": "X"}) is None
    conflict = compare_fact("r1", "winner", {"jolpica": "X", "official_f1": "Y"})
    assert conflict is not None
    assert conflict.resolution == "Y"  # official_f1 outranks jolpica
    assert "official_f1" in conflict.resolution_reason
    custom = compare_fact("r1", "winner", {"jolpica": "X", "official_f1": "Y"},
                          priority=["jolpica", "official_f1"])
    assert custom is not None and custom.resolution == "X"
    found = detect_conflicts([("r1", "winner", {"a": "X", "b": "Y"}),
                              ("r1", "pole", {"a": "Z", "b": "Z"})])
    assert [(c.entity_id, c.field) for c in found] == [("r1", "winner")]


def test_deterministic_outputs() -> None:
    first = validate_bundle("v", results=[{"result_id": "b"}, {"result_id": "a"}])
    second = validate_bundle("v", results=[{"result_id": "a"}, {"result_id": "b"}])
    assert first.errors == second.errors
    registry = AliasRegistry()
    registry.register_entity("c:x", ["X Team", "X"])
    assert registry.canonical_ids() == ["c:x"]
