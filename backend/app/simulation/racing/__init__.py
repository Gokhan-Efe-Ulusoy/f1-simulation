from __future__ import annotations

from app.simulation.racing.battle import BattleEngine
from app.simulation.racing.battle_planner import BattlePlan, BattlePlanner, BattlePlannerConfig
from app.simulation.racing.defense import DefenseModel
from app.simulation.racing.dirty_air import DirtyAirModel
from app.simulation.racing.drs_train import DRSTrainModel
from app.simulation.racing.models import (
    BattleConfig,
    BattleContext,
    BattleDecision,
    BattleResourceState,
    BattleState,
    BattleStateType,
    DefenseConfig,
    DefenseContext,
    DefenseDecision,
    DefenseMode,
    DirtyAirConfig,
    DirtyAirContext,
    DirtyAirEffect,
    DRSTrainConfig,
    DRSTrainContext,
    DRSTrainInfo,
    # Configs
    OvertakeConfig,
    # Contexts
    OvertakeContext,
    OvertakeDecision,
    # Enums
    OvertakePhase,
    SafetyCarPhase,
    SafetyCarRestartConfig,
    SafetyCarRestartContext,
    SafetyCarRestartResult,
)
from app.simulation.racing.overtake import OvertakeEngine
from app.simulation.racing.race_procedure import (
    FirstCornerConfig,
    FirstCornerModel,
    FirstCornerOutcome,
    FormationConfig,
    FormationLapModel,
    FormationResult,
    RedFlagConfig,
    RedFlagDecision,
    RedFlagModel,
    RedFlagState,
    StandingRestartConfig,
    StandingRestartModel,
    StandingRestartResult,
    StandingStartModel,
    StartConfig,
    StartResult,
)
from app.simulation.racing.safety_car_restart import SafetyCarRestartModel
from app.simulation.racing.sectors import (
    SectorState,
    compute_sector_weights,
    sector_gap_trace,
    split_lap_into_sectors,
)

__all__ = [
    # Enums
    "OvertakePhase",
    "BattleStateType",
    "DefenseMode",
    "SafetyCarPhase",
    # Contexts/Decisions
    "OvertakeContext",
    "OvertakeDecision",
    "BattleState",
    "BattleContext",
    "BattleDecision",
    "BattleResourceState",
    "DirtyAirContext",
    "DirtyAirEffect",
    "DRSTrainContext",
    "DRSTrainInfo",
    "DefenseContext",
    "DefenseDecision",
    "SafetyCarRestartContext",
    "SafetyCarRestartResult",
    # Configs
    "OvertakeConfig",
    "BattleConfig",
    "DirtyAirConfig",
    "DRSTrainConfig",
    "DefenseConfig",
    "SafetyCarRestartConfig",
    # Engines/Models
    "OvertakeEngine",
    "BattleEngine",
    "DirtyAirModel",
    "DRSTrainModel",
    "DefenseModel",
    "SafetyCarRestartModel",
    # Phase 8: sectors
    "SectorState",
    "compute_sector_weights",
    "sector_gap_trace",
    "split_lap_into_sectors",
    # Phase 8: race procedure
    "FormationConfig",
    "FormationLapModel",
    "FormationResult",
    "StartConfig",
    "StandingStartModel",
    "StartResult",
    "FirstCornerConfig",
    "FirstCornerModel",
    "FirstCornerOutcome",
    "RedFlagConfig",
    "RedFlagDecision",
    "RedFlagModel",
    "RedFlagState",
    "StandingRestartConfig",
    "StandingRestartModel",
    "StandingRestartResult",
    # Phase 8: battle planning
    "BattlePlan",
    "BattlePlanner",
    "BattlePlannerConfig",
]
