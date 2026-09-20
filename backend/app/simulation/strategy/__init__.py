from __future__ import annotations

from app.simulation.strategy.engine import (
    StrategyEngine,
    StrategyContext,
    StintPlan,
    estimate_pit_stop_loss,
)
from app.simulation.strategy.fuel import (
    EngineMode,
    EngineModeProfile,
    DEFAULT_ENGINE_MODES,
    FuelStrategyOptimizer,
    FuelPlan,
    RaceFuelStrategy,
    AdaptiveFuelManager,
    create_fuel_strategy_for_stints,
)
from app.simulation.strategy.pitstop import (
    PitStopTrigger,
    UndercutAnalysis,
    OvercutAnalysis,
    PitWindow,
    PitStopDecision,
    PitStopStrategyEngine,
    PitStopSimulator,
)
from app.simulation.strategy.evaluator import (
    StrategyEvaluator,
    StrategyComparison,
    StrategyRecommendation,
    LiveStrategyAdvisor,
)
from app.simulation.strategy.team_orders import (
    TeamOrderModel,
    TeamOrderConfig,
    TeamOrderContext,
    TeamOrderDecision,
    ChampionshipContext,
)
from app.simulation.strategy.state import StrategyState, EvidenceTier, build_strategy_state_from_driver  # noqa: E501
from app.simulation.strategy.actions import (
    ActionType,
    StrategyAction,
    PitAction,
    ContinueAction,
    StayOutAction,
    ManageTyresAction,
    ManageFuelAction,
    AttackAction,
    DefendAction,
)
from app.simulation.strategy.candidates import CandidateGenerator, CandidateStrategy
from app.simulation.strategy.pit_window import PitWindowEngine, PitWindowResult
from app.simulation.strategy.opponent_model import OpponentModel, OpponentPrediction
from app.simulation.strategy.decision_engine import DecisionEngine, EvaluationOutput, DecisionOutput
from app.simulation.strategy.explanation import ExplanationEngine
from app.simulation.strategy.rng import strategy_rng, strategy_seed, STRATEGY_RNG_OFFSET
from app.simulation.strategy.tyre_strategy import TyreStrategyEngine
from app.simulation.strategy.weather_strategy import WeatherStrategyEngine
from app.simulation.strategy.race_control_strategy import RaceControlStrategyEngine

STRATEGY_MODEL_VERSION = "strategy-v1.0.0"

__all__ = [
    # Engine
    "StrategyEngine",
    "StrategyContext",
    "StintPlan",
    "estimate_pit_stop_loss",
    # Fuel
    "EngineMode",
    "EngineModeProfile",
    "DEFAULT_ENGINE_MODES",
    "FuelStrategyOptimizer",
    "FuelPlan",
    "RaceFuelStrategy",
    "AdaptiveFuelManager",
    "create_fuel_strategy_for_stints",
    # Pit stop
    "PitStopTrigger",
    "UndercutAnalysis",
    "OvercutAnalysis",
    "PitWindow",
    "PitStopDecision",
    "PitStopStrategyEngine",
    "PitStopSimulator",
    # Evaluator
    "StrategyEvaluator",
    "StrategyComparison",
    "StrategyRecommendation",
    "LiveStrategyAdvisor",
    # Team orders (Phase 7)
    "TeamOrderModel",
    "TeamOrderConfig",
    "TeamOrderContext",
    "TeamOrderDecision",
    "ChampionshipContext",
    # Phase 19 Decision Engine
    "StrategyState",
    "EvidenceTier",
    "build_strategy_state_from_driver",
    "ActionType",
    "StrategyAction",
    "PitAction",
    "ContinueAction",
    "StayOutAction",
    "ManageTyresAction",
    "ManageFuelAction",
    "AttackAction",
    "DefendAction",
    "CandidateGenerator",
    "CandidateStrategy",
    "PitWindowEngine",
    "PitWindowResult",
    "OpponentModel",
    "OpponentPrediction",
    "DecisionEngine",
    "EvaluationOutput",
    "DecisionOutput",
    "ExplanationEngine",
    "strategy_rng",
    "strategy_seed",
    "STRATEGY_RNG_OFFSET",
    "TyreStrategyEngine",
    "WeatherStrategyEngine",
    "RaceControlStrategyEngine",
    "STRATEGY_MODEL_VERSION",
]
