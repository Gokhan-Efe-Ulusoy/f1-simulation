"""Phase 22 — Provenance tests (fingerprints, artifacts, reproducibility)."""
import pytest

from app.simulation.replay.artifacts import (
    experiment_reproducible_from_artifact,
    load_experiment,
    save_experiment,
    save_markdown_report,
)
from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.provenance import model_versions
from app.simulation.scenario.models import Intervention


@pytest.fixture(scope="module")
def engine():
    return ReplayEngine(seed=42, simulations=60)


@pytest.fixture(scope="module")
def experiment(engine):
    hrace = engine.load_race("2024-bahrain")
    did = hrace.grid_order[0]
    return engine.counterfactual(
        "2024-bahrain",
        [Intervention(family="driver", op="ADD_DELTA", target=did,
                      parameter="pace_delta", value=0.5)],
        experiment_id="p22-prov",
        question="Does a +0.5 pace delta move the distribution?",
        laps=6,
    )


REQUIRED_VERSION_KEYS = (
    "MODEL_VERSION", "SIMULATION_VERSION", "RACEENGINE_VERSION",
    "SCENARIO_MODEL_VERSION", "REPLAY_MODEL_VERSION",
    "COUNTERFACTUAL_MODEL_VERSION", "SENSITIVITY_MODEL_VERSION",
    "STRATEGY_MODEL_VERSION", "WEATHER_MODEL_VERSION",
    "RACE_CONTROL_MODEL_VERSION", "SETUP_MODEL_VERSION",
)


def test_provenance_versions_complete(experiment):
    versions = experiment.provenance["versions"]
    for key in REQUIRED_VERSION_KEYS:
        assert versions.get(key), key
    assert versions["REPLAY_MODEL_VERSION"] == "replay-v1.0.0"
    assert experiment.provenance["dataset_hash"]
    assert experiment.provenance["as_of"] < experiment.provenance["race_date"]
    assert model_versions()["MODEL_VERSION"] == "0.9.0"


def test_fingerprint_reproduces_and_changes(engine, experiment):
    hrace = engine.load_race("2024-bahrain")
    did = hrace.grid_order[0]
    rerun = engine.counterfactual(
        "2024-bahrain",
        [Intervention(family="driver", op="ADD_DELTA", target=did,
                      parameter="pace_delta", value=0.5)],
        experiment_id="p22-prov",
        question="Does a +0.5 pace delta move the distribution?",
        laps=6,
    )
    assert rerun.fingerprint == experiment.fingerprint
    changed = engine.counterfactual(
        "2024-bahrain",
        [Intervention(family="driver", op="ADD_DELTA", target=did,
                      parameter="pace_delta", value=1.0)],
        experiment_id="p22-prov",
        question="Does a +0.5 pace delta move the distribution?",
        laps=6,
    )
    assert changed.fingerprint != experiment.fingerprint


def test_metadata_only_change_keeps_fingerprint(engine, experiment):
    # The human question is metadata: same model inputs -> same fingerprint.
    hrace = engine.load_race("2024-bahrain")
    did = hrace.grid_order[0]
    other = engine.counterfactual(
        "2024-bahrain",
        [Intervention(family="driver", op="ADD_DELTA", target=did,
                      parameter="pace_delta", value=0.5)],
        experiment_id="p22-prov",
        question="A completely different title for the same inputs.",
        laps=6,
    )
    assert other.fingerprint == experiment.fingerprint


def test_artifact_roundtrip_reproducible(experiment, tmp_path, monkeypatch):
    import app.simulation.replay.artifacts as A

    monkeypatch.setattr(A, "experiments_dir", lambda: tmp_path)
    monkeypatch.setattr(A, "reports_dir", lambda: tmp_path)
    path = save_experiment(experiment, slug="prov")
    art = load_experiment(path)
    assert art["fingerprint"] == experiment.fingerprint
    assert experiment_reproducible_from_artifact(path) is True
    report = save_markdown_report(experiment, name="p22-prov-report")
    text = report.read_text()
    assert "NON_IDENTIFIABLE" in text
    assert "SIMULATED" in text and "OBSERVED" in text
    assert "MODEL INPUT" in text and "MODEL ASSUMPTION" in text
