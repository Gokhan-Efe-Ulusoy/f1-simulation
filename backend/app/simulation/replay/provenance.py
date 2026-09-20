"""Phase 22 — Experiment provenance + fingerprinting.

Fingerprints cover model-affecting inputs only (scenario content, spec,
versions, seed, N, race, checkpoint). Report metadata (titles, timestamps,
author notes) never affects the fingerprint.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.simulation.replay import (
    REPLAY_MODEL_VERSION,
    COUNTERFACTUAL_MODEL_VERSION,
    SENSITIVITY_MODEL_VERSION,
)


def model_versions() -> dict[str, str]:
    try:
        from app.simulation import version as V

        keys = (
            "MODEL_VERSION", "SIMULATION_VERSION", "RACEENGINE_VERSION",
            "SCENARIO_MODEL_VERSION", "REPLAY_MODEL_VERSION",
            "COUNTERFACTUAL_MODEL_VERSION", "SENSITIVITY_MODEL_VERSION",
            "STRATEGY_MODEL_VERSION", "WEATHER_MODEL_VERSION",
            "WEATHER_CALIBRATION_VERSION", "RACE_CONTROL_MODEL_VERSION",
            "RACE_CONTROL_POLICY_VERSION", "SETUP_MODEL_VERSION",
            "CALIBRATION_VERSION", "DATASET_VERSION", "CONFIG_VERSION",
        )
        out: dict[str, str] = {}
        for key in keys:
            try:
                out[key] = str(getattr(V, key, ""))
            except Exception:
                out[key] = ""
        for key, val in (
            ("REPLAY_MODEL_VERSION", REPLAY_MODEL_VERSION),
            ("COUNTERFACTUAL_MODEL_VERSION", COUNTERFACTUAL_MODEL_VERSION),
            ("SENSITIVITY_MODEL_VERSION", SENSITIVITY_MODEL_VERSION),
        ):
            out.setdefault(key, val)
        return out
    except Exception:
        return {
            "REPLAY_MODEL_VERSION": REPLAY_MODEL_VERSION,
            "COUNTERFACTUAL_MODEL_VERSION": COUNTERFACTUAL_MODEL_VERSION,
            "SENSITIVITY_MODEL_VERSION": SENSITIVITY_MODEL_VERSION,
        }


def dataset_hash() -> str:
    """Short hash of the dataset manifest (content identity, not full data)."""
    try:
        from app.simulation.replay.state_builder import data_root

        raw = (data_root() / "manifests" / "dataset-manifest.json").read_bytes()
        return hashlib.sha256(raw).hexdigest()[:16]
    except Exception:
        return "unknown"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint16(payload: Any) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()[:16]


def experiment_fingerprint(
    race_id: str,
    scenario_content_hash: str,
    spec_payload: Any,
    seed: int,
    simulations: int,
    versions: dict[str, str] | None = None,
) -> str:
    """Fingerprint over model-affecting inputs only."""
    return fingerprint16({
        "race_id": race_id,
        "scenario": scenario_content_hash,
        "spec": spec_payload,
        "seed": int(seed),
        "simulations": int(simulations),
        "versions": versions or model_versions(),
    })


def build_experiment_provenance(
    race_id: str,
    as_of: str,
    race_date: str,
    seed: int,
    simulations: int,
    laps: int,
    checkpoint: str = "finish",
    intervention: Any = None,
    crn: dict[str, Any] | None = None,
    evidence: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import datetime

    prov: dict[str, Any] = {
        "race_id": race_id,
        "as_of": as_of,
        "race_date": race_date,
        "seed": int(seed),
        "N": int(simulations),
        "laps": int(laps),
        "checkpoint": checkpoint,
        "intervention": intervention,
        "crn": crn or {},
        "evidence_tiers": evidence or {},
        "versions": model_versions(),
        "dataset_hash": dataset_hash(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if extra:
        prov.update(extra)
    return prov
