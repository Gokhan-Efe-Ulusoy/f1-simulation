"""Fingerprint for Phase 27 decomposition."""

import hashlib
import json


def fingerprint(
    dataset_version: str,
    dataset_hash: str,
    calibration_version: str,
    model_version: str,
    features: list,
    as_of: str,
    training_window: str,
    seed: int,
    coefficients: dict,
) -> str:
    payload = {
        "dataset_version": dataset_version,
        "dataset_hash": dataset_hash,
        "calibration_version": calibration_version,
        "model_version": model_version,
        "features": sorted(features),
        "as_of": as_of,
        "training_window": training_window,
        "seed": seed,
        "coefficients": coefficients,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]
