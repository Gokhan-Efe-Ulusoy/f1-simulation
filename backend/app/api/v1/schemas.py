"""Phase 28 — API schemas (thin, Pydantic v2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ---- shared ----
class HealthResponse(BaseModel):
    status: str
    version: str
    simulation_model_version: str


class ErrorResponse(BaseModel):
    error: dict[str, Any]


# ---- metadata ----
class MetadataResponse(BaseModel):
    api_version: str
    dataset_version: str
    dataset_hash: str
    calibration_version: str
    tyre_version: str
    weather_version: str
    race_control_version: str
    strategy_version: str
    setup_version: str
    race_engine_version: str
    model_version: str
    simulation_version: str
    config_version: str
    evidence_tiers: dict[str, str]
    provenance: dict[str, Any]


# ---- races ----
class RaceListItem(BaseModel):
    race_id: str
    season_id: str | None = None
    round: int | None = None
    circuit_id: str | None = None
    race_date: str | None = None
    total_laps: int | None = None
    availability: str = "available"
    unavailable: list[str] = Field(default_factory=list)


class RaceListResponse(BaseModel):
    races: list[RaceListItem]
    total: int
    limit: int
    offset: int


class RaceDetailResponse(BaseModel):
    race_id: str
    season_id: str | None = None
    round: int | None = None
    circuit_id: str | None = None
    race_date: str | None = None
    total_laps: int | None = None
    circuit_name: str | None = None
    availability: str
    unavailable: list[str] = Field(default_factory=list)
    driver_count: int | None = None
    evidence_tiers: dict[str, str] | None = None


# ---- simulate/race ----
class RaceSimulationRequest(BaseModel):
    race_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical race_id e.g. 2024-bahrain-grand-prix or track id",
    )
    seed: int | None = Field(
        default=42, ge=-2147483648, le=2147483647, description="Deterministic RNG seed (int32)"
    )
    laps_override: int | None = Field(
        default=None, ge=1, le=200, description="Override total laps (1..200)"
    )
    track_id: str | None = Field(default=None, max_length=50)
    enable_strategy: bool = False
    enable_setup: bool = False
    enable_weather: bool = True
    enable_race_control: bool = False
    save_replay: bool = Field(default=True, description="Persist result for GET /simulation/{id}")
    priority: int = Field(default=50, ge=0, le=100, description="0..100; does NOT affect RNG")

    @field_validator("race_id")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("race_id must not contain path separators")
        return v


class RaceSimulationResponse(BaseModel):
    simulation_id: str
    job_id: str | None = None
    race_id: str
    seed: int | None
    track_id: str | None = None
    total_laps: int | None = None
    classification: list[dict[str, Any]] | None = None
    lap_summary: dict[str, Any] | None = None
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    strategy_summary: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] | None = None
    model_versions: dict[str, str] | None = None
    evidence_tiers: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    reproducibility: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    runtime: dict[str, Any] = Field(default_factory=dict)
    # Phase 29-30: lifecycle + hashing
    status: str = "COMPLETED"
    simulation_type: str = "race"
    request_hash: str | None = None
    result_hash: str | None = None
    execution_time: float | None = None
    execution_metadata: dict[str, Any] | None = None
    poll_url: str | None = None
    progress: float | None = None
    current_stage: str | None = None


# ---- monte carlo ----
class MonteCarloRequest(BaseModel):
    race_id: str = Field(..., min_length=1, max_length=100)
    simulations: int = Field(
        default=1000, ge=1, le=5000, description="Number of simulations (1..5000)"
    )
    seed: int | None = Field(default=42, ge=-2147483648, le=2147483647)
    laps_override: int | None = Field(default=None, ge=1, le=200)
    enable_strategy: bool = Field(
        default=False, description="Enable strategy integration (PRIOR_ONLY)"
    )
    enable_setup: bool = False
    enable_weather: bool = True
    enable_race_control: bool = True
    save_replay: bool = True
    priority: int = Field(default=50, ge=0, le=100, description="0..100, LOW=10 NORMAL=50 HIGH=90; does NOT affect RNG")
    chunk_size: int | None = Field(default=None, ge=1, le=5000, description="Chunk size for deterministic chunked execution")

    @field_validator("race_id")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("race_id must not contain path separators")
        return v


class MonteCarloResponse(BaseModel):
    simulation_id: str
    job_id: str | None = None
    race_id: str
    N: int | None = None
    simulations: int | None = None
    seed: int | None
    win_probabilities: dict[str, float] | None = None
    podium_probabilities: dict[str, float] | None = None
    finish_position_distribution: dict[str, dict[str, float]] | None = None
    dnf_statistics: dict[str, float] | None = None
    expected_points: dict[str, float] | None = None
    uncertainty: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    model_versions: dict[str, str] | None = None
    evidence_tiers: dict[str, str] | None = None
    runtime: dict[str, Any] | None = None
    reproducibility: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    # Phase 29-30
    status: str = "COMPLETED"
    simulation_type: str = "monte_carlo"
    request_hash: str | None = None
    result_hash: str | None = None
    execution_time: float | None = None
    execution_metadata: dict[str, Any] | None = None
    poll_url: str | None = None
    progress: float | None = None
    current_stage: str | None = None
    chunk_manifest: dict[str, Any] | None = None
    chunked: bool | None = None


# ---- strategy ----
class StrategyEvaluateRequest(BaseModel):
    # Either full StrategyState dict or minimal driver state
    state: dict[str, Any] = Field(
        ..., description="StrategyState observable at lap t (no future fields)"
    )
    track_pit_loss: float = Field(default=22.0, ge=0, le=60)
    seed: int | None = Field(default=42, ge=-2147483648, le=2147483647)

    @field_validator("state")
    @classmethod
    def no_leakage(cls, v: dict[str, Any]) -> dict[str, Any]:
        for k in list(v.keys()):
            low = k.lower()
            if "future" in low or "observed_result" in low or "actual_" in low:
                raise ValueError(f"leakage field rejected: {k}")
        return v


class StrategyEvaluateResponse(BaseModel):
    driver_id: str
    lap: int
    recommended_action: dict[str, Any]
    decision: str
    target_compound: str | None = None
    pit_window: list[int] | None = None
    candidate_actions: list[dict[str, Any]]
    evaluations: list[dict[str, Any]]
    uncertainty: float
    confidence: float
    evidence_tier: str
    explanation: dict[str, Any]
    provenance: dict[str, Any]


# ---- scenario ----
class ScenarioCompareRequest(BaseModel):
    race_id: str = Field(..., min_length=1, max_length=100)
    interventions: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=20, description="List of Intervention dicts"
    )
    seed: int | None = Field(default=42, ge=-2147483648, le=2147483647)
    simulations: int = Field(default=100, ge=1, le=5000)
    laps: int | None = Field(default=None, ge=1, le=200)
    experiment_id: str | None = Field(default=None, max_length=100)
    question: str | None = Field(default=None, max_length=500)

    @field_validator("race_id")
    @classmethod
    def no_path(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("race_id must not contain path separators")
        return v

    @field_validator("interventions")
    @classmethod
    def no_leakage_params(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for idx, iv in enumerate(v):
            param = str(iv.get("parameter", ""))
            low = param.lower()
            if any(
                s in low
                for s in (
                    "future_",
                    "observed_result",
                    "actual_",
                    "realized",
                    "final_position",
                    "championship",
                    "standing",
                )
            ):
                raise ValueError(
                    f"intervention {idx} parameter {param!r} rejected: leakage blocklist"
                )
        return v


class ScenarioCompareResponse(BaseModel):
    experiment_id: str
    race_id: str
    seed: int | None
    simulations: int
    trace: list[dict[str, Any]]
    comparison: dict[str, Any] | None = None
    attribution: dict[str, Any] | None = None
    crn_manifest: dict[str, Any] | None = None
    provenance: dict[str, Any]
    evidence: dict[str, str] | None = None
    limitations: list[str] = Field(default_factory=list)
    fingerprint: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ---- replay ----
class ReplayCheckpointResponse(BaseModel):
    race_id: str
    seed: int | None
    simulations: int
    laps: int
    checkpoint: dict[str, Any] | None = None
    checkpoint_name: str | None = None
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint_results: list[dict[str, Any]] = Field(default_factory=list)
    deviation_metrics: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    evidence_summary: dict[str, str] | None = None


# ---- simulation job ----
class SimulationJobResponse(BaseModel):
    simulation_id: str
    job_id: str | None = None
    status: str  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, TIMEOUT (case-insensitive for compat)
    result: dict[str, Any] | None = None
    created_at: str | float | None = None
    updated_at: str | float | None = None
    started_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    failed_at: str | None = None
    timed_out_at: str | None = None
    heartbeat_at: str | None = None
    error: dict[str, Any] | str | None = None
    progress: float | None = None
    current_stage: str | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    priority: int | None = None
    request_hash: str | None = None
    result_hash: str | None = None
    simulation_type: str | None = None
    race_id: str | None = None
    seed: int | None = None
    poll_url: str | None = None
    chunk_count: int | None = None
    completed_chunks: int | None = None
    total_chunks: int | None = None
    chunk_size: int | None = None
