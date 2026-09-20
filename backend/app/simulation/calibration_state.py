"""CalibrationState for Phase 14 — integrates all calibration models into per-race state.

Respects as_of, handles NON_IDENTIFIABLE, propagates uncertainty.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from app.data.calibration_api import (
    get_driver_performance, get_constructor_performance, get_circuit_effect,
    get_qualifying_distribution, get_race_pace_distribution, get_reliability_probability,
    get_overtaking_effect, get_defending_effect, get_weather_effect, get_uncertainty
)
from app.simulation.scenario_v14 import Scenario

ROOT = Path(__file__).resolve().parents[2]
CALIB_ROOT = ROOT / "data" / "calibration"

class CalibrationState(BaseModel if False else object):
    """Per-race calibration state (dict-like for flexibility)."""
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.as_of = scenario.as_of
        self.circuit_id = scenario.circuit_id
        self.era = scenario.provenance.get("era") if hasattr(scenario, "provenance") else None
        # Build from API
        self.drivers: dict[str, dict[str, Any]] = {}
        self.constructors: dict[str, dict[str, Any]] = {}
        self.circuit: dict[str, Any] = {}
        self.era_effect: dict[str, Any] = {}
        self.uncertainty: dict[str, Any] = {}
        self._build()

    def _build(self):
        # Circuit
        self.circuit = get_circuit_effect(self.circuit_id, self.as_of)
        # Era
        try:
            era_data = json.loads((CALIB_ROOT / "models" / "era_model.json").read_text())
            era_name = self.scenario.provenance.get("era") if hasattr(self.scenario, "provenance") else None  # noqa: E501
            # Derive era from season
            season = self.scenario.season_id
            try:
                y=int(season)
                for name, s,e in [("1950-1960",1950,1960),("1961-1970",1961,1970),("1971-1982",1971,1982),("1983-1987",1983,1987),("1988-1993",1988,1993),("1994-1997",1994,1997),("1998-2008",1998,2008),("2009-2013",2009,2013),("2014-2021",2014,2021),("2022-2026",2022,2026)]:  # noqa: E501
                    if s<=y<=e:
                        era_name=name
                        break
            except:
                era_name="2022-2026"
            self.era_effect = era_data.get(era_name, {"era": era_name, "available": False})
        except:
            self.era_effect = {"era": "unknown", "available": False}

        # Drivers and constructors
        for drv in self.scenario.drivers:
            driver_id = drv["driver_id"]
            constr_id = drv.get("constructor_id","")
            # Driver
            d_perf = get_driver_performance(driver_id, self.as_of)
            q_dist = get_qualifying_distribution(driver_id, self.as_of)
            r_dist = get_race_pace_distribution(driver_id, self.as_of)
            rel = get_reliability_probability(driver_id, constr_id, self.as_of)
            over = get_overtaking_effect(driver_id, self.as_of)
            defi = get_defending_effect(driver_id, self.as_of)
            # Handle NON_IDENTIFIABLE: if calibration flags, increase variance
            # Our driver_model already has shrinkage, but we check identifiability via sample_size
            is_weak = d_perf.get("sample_size",0) < 5
            if is_weak:
                # Widen uncertainty
                if d_perf.get("uncertainty"):
                    d_perf["uncertainty"]["std"] = (d_perf["uncertainty"]["std"] or 1.0) * 1.5

            self.drivers[driver_id] = {
                "driver_id": driver_id,
                "pace": d_perf,
                "qualifying": q_dist,
                "race_pace": r_dist,
                "reliability": rel,
                "overtaking": over,
                "defending": defi,
                "uncertainty": d_perf.get("uncertainty"),
                "sample_size": d_perf.get("sample_size",0),
                "evidence_tier": d_perf.get("evidence_tier","C"),
                "provenance": {
                    "driver_id": driver_id,
                    "as_of": self.as_of,
                    "dataset_version": "f1-dataset-v1.1",
                    "calibration_version": "calibration-v1.0.0",
                    "evidence_tier": d_perf.get("evidence_tier","C"),
                },
                # Explicit missingness
                "available": d_perf.get("value") is not None,
                "variance_tier": "estimated" if d_perf.get("value") is not None else "prior_only",
            }
            # Constructor (shared per driver, but also per constructor)
            if constr_id and constr_id not in self.constructors:
                c_perf = get_constructor_performance(constr_id, self.as_of)
                self.constructors[constr_id] = {
                    "constructor_id": constr_id,
                    "pace": c_perf,
                    "reliability": c_perf,  # constructor reliability is in same
                    "sample_size": c_perf.get("sample_size",0),
                    "evidence_tier": c_perf.get("evidence_tier","C"),
                    "provenance": {"constructor_id": constr_id, "as_of": self.as_of},
                    "available": c_perf.get("value") is not None,
                }

        # Weather: check availability
        self.weather = get_weather_effect(self.as_of)
        # Tyre: from tyre_model
        try:
            tyre_data = json.loads((CALIB_ROOT / "models" / "tyre_model.json").read_text())
            self.tyre = tyre_data
        except:
            self.tyre = {"available": False}

        # Telemetry
        try:
            tel = json.loads((CALIB_ROOT / "models" / "telemetry_info.json").read_text())
            self.telemetry = tel
        except:
            self.telemetry = {"available": False}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario.scenario_id,
            "as_of": self.as_of,
            "circuit": self.circuit,
            "era": self.era_effect,
            "drivers": self.drivers,
            "constructors": self.constructors,
            "weather": self.weather,
            "tyre": self.tyre,
            "telemetry": getattr(self, "telemetry", {}),
            "provenance": {
                "dataset_version": "f1-dataset-v1.1",
                "calibration_version": "calibration-v1.0.0",
                "as_of": self.as_of,
                "temporal_policy": "strict_before",
            },
            # Preserve per-parameter provenance
            "parameter_provenance": {did: v["provenance"] for did, v in self.drivers.items()},
        }

def build_calibration_state(scenario: Scenario) -> dict[str, Any]:
    cs = CalibrationState(scenario)
    return cs.to_dict()
