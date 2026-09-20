"""Phase 22 — Replay / experiment data models.

Serializable (pydantic) contracts only; no simulation logic. Every observed
or assumed quantity carries source + evidence tier + timestamps. Nothing here
may fabricate historical information: unavailable quantities are None with
tier NON_IDENTIFIABLE (or PRIOR_ONLY for explicit model priors).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceTier = Literal[
    "CALIBRATED", "LIMITED", "PRIOR_ONLY", "NON_IDENTIFIABLE", "NOT_TESTABLE",
]

TIER_ORDER: dict[str, int] = {
    "CALIBRATED": 4,
    "LIMITED": 3,
    "PRIOR_ONLY": 2,
    "NON_IDENTIFIABLE": 1,
    "NOT_TESTABLE": 0,
}


class ObservedValue(BaseModel):
    """One quantity with its provenance. value=None means unknown."""

    value: Any = None
    source: str = ""
    evidence_tier: str = "NON_IDENTIFIABLE"
    observation_timestamp: str = ""
    as_of: str = ""

    model_config = {"use_enum_values": True}


class HistoricalObservationState(BaseModel):
    """Only information available at observation lap `lap`.

    `lap=0` means pre-race. Future realized events (result, future pits,
    future weather, future race-control, future telemetry) are NEVER stored
    here; they live only in validation targets outside the decision layer.
    """

    race_id: str
    season: str = ""
    round: int | None = None
    circuit_id: str = ""
    lap: int = 0
    race_date: str = ""
    as_of: str = ""
    grid_order: ObservedValue = Field(default_factory=ObservedValue)
    drivers: ObservedValue = Field(default_factory=ObservedValue)
    weather_current: ObservedValue = Field(default_factory=ObservedValue)
    weather_forecast_summary: ObservedValue = Field(default_factory=ObservedValue)
    race_control_phase: ObservedValue = Field(default_factory=ObservedValue)
    sector_flags: ObservedValue = Field(default_factory=ObservedValue)
    tyre_state: ObservedValue = Field(default_factory=ObservedValue)
    tyre_age: ObservedValue = Field(default_factory=ObservedValue)
    fuel_state: ObservedValue = Field(default_factory=ObservedValue)
    driver_pace_estimate: ObservedValue = Field(default_factory=ObservedValue)
    constructor_pace_estimate: ObservedValue = Field(default_factory=ObservedValue)
    pit_history_observed_until_t: ObservedValue = Field(default_factory=ObservedValue)
    incident_history_observed_until_t: ObservedValue = Field(default_factory=ObservedValue)
    strategy_state: ObservedValue = Field(default_factory=ObservedValue)
    setup_state: ObservedValue = Field(default_factory=ObservedValue)
    # Structural guard: the realized result is excluded by construction.
    realized_result_excluded: bool = True

    model_config = {"use_enum_values": True}

    def evidence_summary(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in (
            "grid_order", "drivers", "weather_current",
            "weather_forecast_summary", "race_control_phase", "sector_flags",
            "tyre_state", "tyre_age", "fuel_state", "driver_pace_estimate",
            "constructor_pace_estimate", "pit_history_observed_until_t",
            "incident_history_observed_until_t", "strategy_state",
            "setup_state",
        ):
            out[name] = getattr(self, name).evidence_tier
        return out


class HistoricalRace(BaseModel):
    """A historical race with its observation cutoff + validation target.

    `observed_result` is a post-hoc validation target ONLY and must never be
    passed to the simulation decision layer.
    """

    race_id: str
    season_id: str = ""
    round: int | None = None
    circuit_id: str = ""
    race_date: str = ""
    as_of: str = ""
    total_laps: int | None = None
    total_laps_tier: str = "NON_IDENTIFIABLE"
    scenario_id: str = ""
    grid_order: list[str] = Field(default_factory=list)
    drivers: list[dict[str, Any]] = Field(default_factory=list)
    observed_result: dict[str, Any] = Field(default_factory=dict)
    observed_result_validation_only: bool = True
    unavailable: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, str] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class CheckpointResult(BaseModel):
    """One truncated-horizon replay leg."""

    name: str
    lap: int
    simulations: int
    seed: int
    fingerprint: str = ""
    top_driver_by_win_prob: str = ""
    top_win_probability: float = 0.0
    provenance: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class DeviationMetrics(BaseModel):
    """Baseline replay vs observed result (post-hoc, never an input)."""

    predicted_winner: str = ""
    observed_winner: str = ""
    winner_match: bool = False
    top3_overlap: int = 0
    finish_mae: float | None = None
    finish_mae_drivers: int = 0
    dnf_mismatch: float | None = None
    pit_count_mismatch: str = "NON_IDENTIFIABLE"
    lap_time_mae: str = "NON_IDENTIFIABLE"
    coverage: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class ReplayResult(BaseModel):
    """Baseline replay bundle for one historical race."""

    race_id: str
    seed: int = 42
    simulations: int = 0
    laps: int = 0
    baseline_fingerprint: str = ""
    checkpoint_results: list[CheckpointResult] = Field(default_factory=list)
    deviation_metrics: DeviationMetrics | None = None
    observed_result: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, str] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class CRNManifest(BaseModel):
    """Common-random-numbers configuration for one experiment."""

    experiment_id: str = ""
    baseline_seed: int = 42
    counterfactual_seed: int = 42
    same_seed: bool = True
    simulations: int = 0
    stream_manifest: dict[str, str] = Field(default_factory=dict)
    unrelated_streams_unchanged: bool = True

    model_config = {"use_enum_values": True}


class AttributionLevel(BaseModel):
    """One attribution level: what the model actually measured."""

    direct: list[str] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)
    final: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class InterventionAttribution(BaseModel):
    """Model-attributed (never real-world causal) reading of an experiment."""

    experiment_id: str = ""
    intervention: str = ""
    what_changed: list[str] = Field(default_factory=list)
    where_changed: list[str] = Field(default_factory=list)
    downstream: AttributionLevel = Field(default_factory=AttributionLevel)
    evidence_tier: str = "PRIOR_ONLY"
    disclaimer: str = (
        "Model-attributed effect under the stated assumptions and available "
        "evidence; not a real-world causal claim."
    )

    model_config = {"use_enum_values": True}


class ExtendedDriverDelta(BaseModel):
    """Per-driver distribution contrast (counterfactual - baseline)."""

    driver_id: str
    d_win_probability: float = 0.0
    d_podium_probability: float = 0.0
    d_top10_probability: float = 0.0
    d_expected_finish: float = 0.0
    d_median_finish: float = 0.0
    d_dnf_probability: float = 0.0
    d_expected_points: float = 0.0
    d_quantile_10: float = 0.0
    d_quantile_25: float = 0.0
    d_quantile_50: float = 0.0
    d_quantile_75: float = 0.0
    d_quantile_90: float = 0.0
    l1_finish_distribution: float = 0.0
    relative_win_delta: float | None = None
    baseline_win_probability: float = 0.0
    counterfactual_win_probability: float = 0.0
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}


class ExtendedComparison(BaseModel):
    """Extended baseline-vs-counterfactual comparison (Phase 21 + quantiles)."""

    spec_id: str
    experiment_id: str = ""
    baseline_fingerprint: str = ""
    counterfactual_fingerprint: str = ""
    seed: int = 42
    simulations: int = 0
    common_random_numbers: bool = True
    driver_deltas: list[ExtendedDriverDelta] = Field(default_factory=list)
    race_effects: dict[str, Any] = Field(default_factory=dict)
    pit_counts: dict[str, Any] = Field(default_factory=dict)
    unmeasurable: dict[str, str] = Field(default_factory=dict)
    evidence_tiers: dict[str, str] = Field(default_factory=dict)
    metric_notes: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class SensitivityPoint(BaseModel):
    """One grid point of a sensitivity sweep."""

    parameter: str = ""
    value: Any = None
    target: str = ""
    d_win_probability: float = 0.0
    d_expected_finish: float = 0.0
    l1_finish_distribution: float = 0.0
    uncertainty_note: str = ""
    evidence_tier: str = "PRIOR_ONLY"

    model_config = {"use_enum_values": True}


class SensitivityResult(BaseModel):
    """One-factor-at-a-time (or bounded grid) sweep outcome."""

    experiment_id: str = ""
    method: str = "one_factor_at_a_time"
    family: str = ""
    parameter: str = ""
    target: str = ""
    points: list[SensitivityPoint] = Field(default_factory=list)
    baseline_fingerprint: str = ""
    seed: int = 42
    simulations: int = 0
    evidence_tier: str = "PRIOR_ONLY"
    limitations: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class SanityCheck(BaseModel):
    """One physical/monotonicity sanity check outcome."""

    name: str
    status: str = "NOT_TESTABLE"
    detail: str = ""
    evidence_tier: str = "PRIOR_ONLY"
    measured: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


class CounterfactualExperiment(BaseModel):
    """Reproducible experiment bundle (machine-readable artifact content)."""

    experiment_id: str
    race_id: str = ""
    question: str = ""
    seed: int = 42
    simulations: int = 0
    laps: int = 0
    spec: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    baseline_fingerprint: str = ""
    counterfactual_fingerprint: str = ""
    comparison: ExtendedComparison | None = None
    attribution: InterventionAttribution | None = None
    sensitivity: SensitivityResult | None = None
    crn_manifest: CRNManifest | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str = ""

    model_config = {"use_enum_values": True}
