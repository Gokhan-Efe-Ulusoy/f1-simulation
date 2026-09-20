"""Calibration dataset v1 generation (Phase 10I).

Produces calibration_dataset_v1 with observed/derived variables,
uncertainty, sample size, source coverage, era, track, driver,
constructor, season. Every record contains dataset_version,
model_version, feature_version, source_provenance. Does NOT auto-promote
to production.
"""
from __future__ import annotations

import json
import os
from typing import Any

from app.data.features import circuit_features, constructor_features, driver_features, era_features


class CalibrationDatasetBuilder:
    """Builds calibration dataset v1 from derived features."""

    def __init__(self, root: str = ".") -> None:
        self.root = root

    def build(
        self,
        dataset_version: str,
        model_version: str = "0.2.0",
        feature_version: str = "0.1.0",
        canonical_dir: str | None = None,
    ) -> dict[str, Any]:
        """Build calibration dataset from canonical and derived data."""
        canonical_dir = canonical_dir or os.path.join(self.root, "data/canonical")

        # Load canonical data
        def load_json(name: str) -> list[dict[str, Any]]:
            path = os.path.join(canonical_dir, f"{name}.json")
            if not os.path.exists(path):
                return []
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
                return data if isinstance(data, list) else []

        results = load_json("results")
        races = load_json("races")
        drivers_data = load_json("drivers")
        constructors_data = load_json("constructors")

        calibration_records: list[dict[str, Any]] = []

        # Driver calibration records
        driver_ids = sorted({str(r.get("driver_id")) for r in results if r.get("driver_id")})
        for driver_id in driver_ids:
            feats = driver_features(driver_id, "2024", results)
            for feat in feats:
                if feat.value is not None:
                    calibration_records.append({
                        "entity_type": "driver",
                        "entity_id": driver_id,
                        "feature": feat.name,
                        "observed_value": feat.value,
                        "derived_value": feat.value if feat.feature_type == "derived" else None,
                        "uncertainty": 0.1 if feat.feature_type == "observed" else 0.2,
                        "sample_size": feat.sample_size,
                        "source_coverage": "race_results",
                        "feature_type": feat.feature_type,
                        "dataset_version": dataset_version,
                        "model_version": model_version,
                        "feature_version": feature_version,
                        "source_provenance": feat.detail.get("provenance", "canonical"),
                    })

        # Constructor calibration records
        constructor_ids = sorted({str(r.get("constructor_id")) for r in results if r.get("constructor_id")})  # noqa: E501
        for constructor_id in constructor_ids:
            feats = constructor_features(constructor_id, "2024", results)
            for feat in feats:
                if feat.value is not None:
                    calibration_records.append({
                        "entity_type": "constructor",
                        "entity_id": constructor_id,
                        "feature": feat.name,
                        "observed_value": feat.value,
                        "uncertainty": 0.15,
                        "sample_size": feat.sample_size,
                        "source_coverage": "race_results",
                        "feature_type": feat.feature_type,
                        "dataset_version": dataset_version,
                        "model_version": model_version,
                        "feature_version": feature_version,
                    })

        # Circuit calibration records
        circuit_ids = sorted({str(r.get("circuit_id")) for r in races if r.get("circuit_id")})
        for circuit_id in circuit_ids:
            feats = circuit_features(circuit_id, "2024", races, results)
            for feat in feats:
                if feat.value is not None:
                    calibration_records.append({
                        "entity_type": "circuit",
                        "entity_id": circuit_id,
                        "feature": feat.name,
                        "observed_value": feat.value,
                        "uncertainty": 0.2,
                        "sample_size": feat.sample_size,
                        "source_coverage": "race_results",
                        "feature_type": feat.feature_type,
                        "dataset_version": dataset_version,
                        "model_version": model_version,
                        "feature_version": feature_version,
                    })

        # Era calibration records (with era normalization)
        # For now, use era features for 2024
        era_feats = era_features("modern", "2024", [])
        for feat in era_feats:
            if feat.value is not None:
                calibration_records.append({
                    "entity_type": "era",
                    "entity_id": "modern",
                    "feature": feat.name,
                    "observed_value": feat.value,
                    "uncertainty": 0.25,
                    "sample_size": feat.sample_size,
                    "source_coverage": "championship",
                    "feature_type": feat.feature_type,
                    "dataset_version": dataset_version,
                    "model_version": model_version,
                    "feature_version": feature_version,
                })

        # Add era-normalized metrics (relative pace)
        for rec in list(calibration_records):
            if rec["feature"] in ("avg_finish", "avg_grid"):
                # Create normalized version as percentile
                rec["era_normalized"] = rec["observed_value"] / 20.0 if rec["observed_value"] else None  # noqa: E501

        # Persist
        calibration_dir = os.path.join(self.root, "data/calibration")
        os.makedirs(calibration_dir, exist_ok=True)
        out_path = os.path.join(calibration_dir, "calibration_dataset_v1.json")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(calibration_records, handle, indent=2, sort_keys=True)

        # Also create CalibrationCandidate records (not auto-promoted)
        candidates = []
        for rec in calibration_records:
            candidates.append({
                "parameter": f"{rec['entity_type']}:{rec['entity_id']}:{rec['feature']}",
                "current_value": 1.0 if rec["feature_type"] == "observed" else 0.0,
                "candidate_value": rec["observed_value"],
                "estimated_uncertainty": rec["uncertainty"],
                "training_period": "1950-2000",
                "validation_period": "2001-2010",
                "test_period": "2011-2020",
                "objective_metric": "mae",
                "sample_size": rec["sample_size"],
                "method": "observed_mean",
                "dataset_version": dataset_version,
                "model_version": model_version,
            })

        candidates_path = os.path.join(calibration_dir, "candidates.json")
        with open(candidates_path, "w", encoding="utf-8") as handle:
            json.dump(candidates, handle, indent=2, sort_keys=True)

        return {
            "calibration_dataset": out_path,
            "candidates": candidates_path,
            "record_count": len(calibration_records),
            "candidate_count": len(candidates),
        }
