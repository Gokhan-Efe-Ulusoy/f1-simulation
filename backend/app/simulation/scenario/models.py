"""Phase 21 — Scenario & counterfactual data model.

Canonical, serializable representation of baseline + interventions +
comparison. No simulation logic here (see compiler.py / engine.py).
Reuses Phase 14 ScenarioType vocabulary: historical / counterfactual /
hypothetical / future.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


ScenarioType = Literal["historical", "counterfactual", "hypothetical", "future"]


class InterventionOp(str, Enum):
    """Controlled intervention vocabulary (only ops actually implemented)."""

    SET_VALUE = "SET_VALUE"
    ADD_DELTA = "ADD_DELTA"
    MULTIPLY = "MULTIPLY"
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"


class InterventionFamily(str, Enum):
    """Intervention families with verified propagation paths."""

    SETUP = "setup"
    STRATEGY = "strategy"  # pit-lap level only (see registry)
    TYRE = "tyre"  # compound level only (see registry)
    RACE_CONTROL = "race_control"
    WEATHER = "weather"
    DRIVER = "driver"  # pace-delta model interventions
    CAR = "car"  # constructor pace-delta model interventions


class Intervention(BaseModel):
    """One explicit, validated modification to a baseline scenario."""

    intervention_id: str = ""
    family: InterventionFamily
    op: InterventionOp
    target: str = "all"  # driver_id | constructor_id | "race" | "all"
    parameter: str
    value: Any = None
    reason: str = ""
    # Filled at compile time (never trusted from user input):
    baseline_value: Any = None
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}

    def key(self) -> tuple[str, str, str]:
        fam = self.family.value if hasattr(self.family, "value") else str(self.family)
        return (fam, str(self.target), str(self.parameter))

    def describe(self) -> str:
        fam = self.family.value if hasattr(self.family, "value") else str(self.family)
        op = self.op.value if hasattr(self.op, "value") else str(self.op)
        return f"{fam}.{self.parameter} [{self.target}] {op} {self.baseline_value} -> {self.value}"


class ScenarioSpec(BaseModel):
    """Immutable counterfactual specification: baseline + ordered interventions."""

    spec_id: str
    baseline_scenario_id: str
    scenario_type: ScenarioType = "counterfactual"
    interventions: list[Intervention] = Field(default_factory=list)
    seed: int = 42
    simulations: int = 100
    reason: str = ""

    model_config = {"use_enum_values": True}


class InterventionTrace(BaseModel):
    """What the compiler changed, in order (for debugging / provenance)."""

    def describe(self) -> str:
        def _num(v: Any) -> str:
            try:
                return f"{float(v):.3f}" if isinstance(v, (int, float)) else str(v)
            except Exception:
                return str(v)

        return (
            f"{self.family}.{self.parameter} [{self.target}] {self.op}: "
            f"{_num(self.baseline_value)} -> {_num(self.counterfactual_value)} "
            f"({self.evidence_tier})"
        )

    intervention_id: str
    family: str
    op: str
    target: str
    parameter: str
    baseline_value: Any = None
    counterfactual_value: Any = None
    modifier_path: str = ""  # e.g. hypothetical_modifiers.setup.drivers.VER
    affected_pathways: list[str] = Field(default_factory=list)
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}


class DriverEffect(BaseModel):
    """Per-driver counterfactual contrast (all deltas = counterfactual - baseline)."""

    driver_id: str
    d_win_probability: float = 0.0
    d_podium_probability: float = 0.0
    d_expected_finish: float = 0.0
    d_median_finish: float = 0.0
    d_dnf_probability: float = 0.0
    d_expected_points: float = 0.0
    l1_finish_distribution: float = 0.0
    d_quantile_25: float = 0.0
    d_quantile_50: float = 0.0
    d_quantile_75: float = 0.0
    baseline_win_probability: float = 0.0
    counterfactual_win_probability: float = 0.0
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}


class ScenarioComparison(BaseModel):
    """Structured baseline-vs-counterfactual comparison (no invented metrics)."""

    spec_id: str
    baseline_fingerprint: str = ""
    counterfactual_fingerprint: str = ""
    seed: int = 42
    simulations: int = 0
    common_random_numbers: bool = True
    driver_effects: list[DriverEffect] = Field(default_factory=list)
    constructor_effects: dict[str, dict[str, float]] = Field(default_factory=dict)
    race_effects: dict[str, Any] = Field(default_factory=dict)
    # e.g. {"sc_cell_count": {"baseline": n, "counterfactual": m, "delta": d}, ...}
    evidence_tiers: dict[str, str] = Field(default_factory=dict)
    metric_notes: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class ScenarioExplanation(BaseModel):
    """Model-implied (never causally-identified) reading of a comparison."""

    spec_id: str
    what_changed: list[str] = Field(default_factory=list)
    why_changed: list[str] = Field(default_factory=list)
    how_much: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    pathways: dict[str, list[str]] = Field(default_factory=dict)
    disclaimer: str = (
        "Model-implied effect under the stated assumptions; "
        "not a causally identified empirical effect."
    )

    model_config = {"use_enum_values": True}


class ScenarioResult(BaseModel):
    """Counterfactual run bundle (references engine outputs, doesn't duplicate them)."""

    spec_id: str
    scenario_type: str = "counterfactual"
    baseline_fingerprint: str = ""
    counterfactual_fingerprint: str = ""
    seed: int = 42
    simulations: int = 0
    trace: list[InterventionTrace] = Field(default_factory=list)
    comparison: ScenarioComparison | None = None
    explanation: ScenarioExplanation | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True, "arbitrary_types_allowed": True}
