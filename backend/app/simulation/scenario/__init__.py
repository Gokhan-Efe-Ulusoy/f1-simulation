"""Phase 21 — Counterfactual & Scenario Engine.

Orchestrates controlled interventions on top of the existing simulation
pipeline (setup / strategy+tyre schedules / race control / weather /
driver+car pace). Reuses domain engines; adds no new physics.
"""
from __future__ import annotations

from app.simulation.scenario.models import (
    DriverEffect,
    Intervention,
    InterventionFamily,
    InterventionOp,
    InterventionTrace,
    ScenarioComparison,
    ScenarioExplanation,
    ScenarioResult,
    ScenarioSpec,
)
from app.simulation.scenario.registry import (
    FAMILY_OPS,
    FAMILY_PARAMS,
    FAMILY_TIERS,
    PATHWAYS,
    TYRE_COMPOUNDS,
    era_support,
)
from app.simulation.scenario.validation import (
    ScenarioValidationError,
    check_spec,
    validate_intervention,
    validate_spec,
)
from app.simulation.scenario.compiler import (
    baseline_fingerprint,
    build_branch_specs,
    compile_spec,
    scenario_content_hash,
    spec_fingerprint,
)
from app.simulation.scenario.resolvers import (
    default_pit_laps,
    resolve_pace_deltas,
    resolve_pit_schedule,
)
from app.simulation.scenario.comparison import compare_results
from app.simulation.scenario.engine import ScenarioEngine, build_explanation

__all__ = [
    "DriverEffect",
    "Intervention",
    "InterventionFamily",
    "InterventionOp",
    "InterventionTrace",
    "ScenarioComparison",
    "ScenarioEngine",
    "ScenarioExplanation",
    "ScenarioResult",
    "ScenarioSpec",
    "FAMILY_OPS",
    "FAMILY_PARAMS",
    "FAMILY_TIERS",
    "PATHWAYS",
    "TYRE_COMPOUNDS",
    "ScenarioValidationError",
    "baseline_fingerprint",
    "build_branch_specs",
    "build_explanation",
    "check_spec",
    "compare_results",
    "compile_spec",
    "default_pit_laps",
    "era_support",
    "resolve_pace_deltas",
    "resolve_pit_schedule",
    "scenario_content_hash",
    "spec_fingerprint",
    "validate_intervention",
    "validate_spec",
]

# Version
SCENARIO_MODEL_VERSION = "scenario-v1.0.0"
