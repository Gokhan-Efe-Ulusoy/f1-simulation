"""Main lap-time decomposition engine — Phase 27."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.simulation.laptime.models import LapRecord, DecompositionComponents, IdentifiabilityTier
from app.simulation.laptime.baseline import CircuitBaseline
from app.simulation.laptime.effects import (
    DriverEffect,
    ConstructorEffect,
    ProgressionEffect,
    TyreEffect,
    PitEffect,
    WeatherEffect,
    RaceControlEffect,
)


class LapTimeDecomposition:
    """Modular decomposition; only include component if identifiable."""

    def __init__(self):
        self.circuit = CircuitBaseline()
        self.driver = DriverEffect()
        self.constructor = ConstructorEffect()
        self.progression = ProgressionEffect()
        self.tyre = TyreEffect()
        self.pit = PitEffect()
        self.weather = WeatherEffect()
        self.race_control = RaceControlEffect()
        self.fitted: Dict[str, dict] = {}
        self.tiers: Dict[str, str] = {}

    def fit(self, records: List[LapRecord]) -> dict:
        # Fit order matters for confounding control
        # 1. circuit baseline (hierarchical)
        cb = self.circuit.fit(records)
        self.fitted["circuit"] = cb
        self.tiers["circuit"] = cb.get("evidence_tier", "LIMITED")

        # 2. driver (circuit-adjusted)
        dr = self.driver.fit(records, self.circuit)
        self.fitted["driver"] = dr
        self.tiers["driver"] = dr.get("evidence_tier", "LIMITED")

        # 3. constructor (circuit+driver adjusted, check identifiability)
        co = self.constructor.fit(records, self.circuit, self.driver)
        self.fitted["constructor"] = co
        self.tiers["constructor"] = co.get("status", "NON_IDENTIFIABLE")

        # 4. progression (associational, not fuel)
        prog = self.progression.fit(records)
        self.fitted["progression"] = prog
        self.tiers["progression"] = prog.get("tier", "RACE_PROGRESSION_ASSOCIATIONAL")

        # 5. tyre reassessment with monotonic constraint
        ty = self.tyre.fit(records)
        self.fitted["tyre"] = ty
        self.tiers["tyre"] = ty.get("tier", "NON_IDENTIFIABLE")

        # 6. pit
        pit = self.pit.fit(records)
        self.fitted["pit"] = pit
        self.tiers["pit"] = pit.get("tier", "LIMITED")

        # 7. weather
        we = self.weather.fit(records)
        self.fitted["weather"] = we
        self.tiers["weather"] = we.get("tier", "PRIOR_ONLY")

        # 8. race control
        rc = self.race_control.fit(records)
        self.fitted["race_control"] = rc
        self.tiers["race_control"] = rc.get("status", "PRIOR_ONLY")

        # Fuel remains NON_IDENTIFIABLE
        self.tiers["fuel"] = "NON_IDENTIFIABLE"

        return {
            "tiers": self.tiers,
            "coefficients": self.fitted,
            "identifiable": {k: v for k, v in self.tiers.items() if v in ("CALIBRATED", "LIMITED")},
            "non_identifiable": {k: v for k, v in self.tiers.items() if v == "NON_IDENTIFIABLE"},
        }

    def predict(self, record: LapRecord) -> DecompositionComponents:
        comp = DecompositionComponents()
        # circuit
        comp.circuit_baseline = self.circuit.predict(record.circuit, record.season)
        # driver
        comp.driver_effect = self.driver.predict(record.driver_number)
        # constructor (if calibrated)
        cons_data = self.fitted.get("constructor", {}).get("constructors", {}).get(record.constructor)  # noqa: E501
        if cons_data and cons_data.get("tier") == "CALIBRATED":
            comp.constructor_effect = cons_data.get("estimate", 0.0)
        # progression associational (not fuel)
        prog_beta = self.fitted.get("progression", {}).get("beta_race_progress")
        if prog_beta and record.lap_number:
            # need max_lap per race — approximate 60
            prog = record.lap_number / 60.0
            comp.race_progression_effect = prog_beta * prog
        # tyre — only if monotonic constrained passes
        tyre_beta = self.fitted.get("tyre", {}).get("constrained_beta")
        if tyre_beta and record.tyre_age is not None:
            # constrained beta >=0, so adds time
            comp.tyre_effect = tyre_beta * record.tyre_age
        # pit
        if record.is_pit_in or record.is_pit_out:
            comp.pit_context = self.pit.mean_loss
        # weather
        if record.is_wet:
            comp.weather_effect = self.fitted.get("weather", {}).get("wet_effect_seconds", 0.0) or 0.0  # noqa: E501
        # race control
        rc_flags = self.fitted.get("race_control", {}).get("flags", {})
        if record.race_control_flag != "GREEN":
            info = rc_flags.get(record.race_control_flag)
            if info and info.get("tier") in ("LIMITED", "CALIBRATED"):
                comp.neutralisation_effect = info.get("mean", 0) - self.circuit.global_mean if hasattr(self.circuit, "global_mean") else 0  # noqa: E501
        # residual not computed here
        comp.total_predicted = (
            comp.circuit_baseline
            + comp.driver_effect
            + comp.constructor_effect
            + comp.tyre_effect
            + comp.race_progression_effect
            + comp.neutralisation_effect
            + comp.pit_context
            + comp.weather_effect
        )
        return comp
