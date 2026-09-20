"""Phase 29 — Stable internal result representation."""

from __future__ import annotations

from typing import Any

from app.simulation.version import MODEL_VERSION, RACEENGINE_VERSION, SIMULATION_VERSION


def normalize_race_result(raw: dict[str, Any], execution_time: float, request_hash: str) -> dict[str, Any]:  # noqa: E501
    """Distinguish execution metadata, race output, provenance."""
    # raw is already API dict from simulation_service
    return {
        "execution_metadata": {
            "simulation_id": raw.get("simulation_id"),
            "status": "COMPLETED",
            "seed": raw.get("seed"),
            "sample_count": None,
            "execution_time": execution_time,
            "engine_version": RACEENGINE_VERSION,
            "model_version": MODEL_VERSION,
            "simulation_version": SIMULATION_VERSION,
            "dataset_version": raw.get("provenance", {}).get("dataset_version", "f1-dataset-v1.3"),
            "dataset_hash": "sha256:canonical-races-v1.3",
            "request_hash": request_hash,
            "result_hash": None,  # filled after
        },
        "race_output": {
            "finishing_order": [c.get("driver_id") for c in (raw.get("classification") or [])],
            "driver_results": raw.get("classification"),
            "positions": {c.get("driver_id"): c.get("position") for c in (raw.get("classification") or [])},  # noqa: E501
            "dnf": [c for c in (raw.get("classification") or []) if str(c.get("status")).lower() in ("retired", "dnf")],  # noqa: E501
            "laps": raw.get("lap_summary"),
            "pit": None,  # engine does not yet produce structured pit per lap
            "weather": None,
            "race_control": None,
        },
        "provenance": raw.get("provenance"),
        "evidence_tiers": raw.get("evidence_tiers"),
        "warnings": raw.get("warnings"),
        "raw": raw,
    }


def normalize_montecarlo_result(raw: dict[str, Any], execution_time: float, request_hash: str) -> dict[str, Any]:  # noqa: E501
    return {
        "execution_metadata": {
            "simulation_id": raw.get("simulation_id"),
            "status": "COMPLETED",
            "seed": raw.get("seed"),
            "sample_count": raw.get("simulations") or raw.get("N"),
            "execution_time": execution_time,
            "engine_version": raw.get("provenance", {}).get("engine_version", RACEENGINE_VERSION),
            "model_version": raw.get("provenance", {}).get("model_version", MODEL_VERSION),
            "simulation_version": SIMULATION_VERSION,
            "dataset_version": raw.get("provenance", {}).get("dataset_version", "f1-dataset-v1.3"),
            "dataset_hash": "sha256:canonical-races-v1.3",
            "request_hash": request_hash,
            "result_hash": None,
        },
        "monte_carlo_output": {
            "win_probability": raw.get("win_probabilities"),
            "podium_probability": raw.get("podium_probabilities"),
            "finish_distribution": raw.get("finish_position_distribution"),
            "dnf_probability": raw.get("dnf_statistics"),
            "quantiles": {k: v.get("finish_CI95") for k, v in (raw.get("distribution") or {}).items()},  # noqa: E501
            "uncertainty": raw.get("uncertainty"),
        },
        "provenance": raw.get("provenance"),
        "evidence_tiers": raw.get("evidence_tiers"),
        "warnings": raw.get("warnings"),
        "raw": raw,
    }
