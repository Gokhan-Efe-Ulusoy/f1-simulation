"""DecisionEngine — leakage-safe, isolated RNG, explainable, Monte Carlo aware."""
from __future__ import annotations

import time
from typing import Any
import numpy as np

from app.simulation.strategy.state import StrategyState, EvidenceTier
from app.simulation.strategy.actions import ActionType, PitAction, ContinueAction, StrategyAction
from app.simulation.strategy.candidates import CandidateGenerator, CandidateStrategy
from app.simulation.strategy.pit_window import PitWindowEngine
from app.simulation.strategy.opponent_model import OpponentModel
from app.simulation.strategy.explanation import ExplanationEngine
from app.simulation.strategy.rng import strategy_rng
from app.simulation.tyre.calibration import load_tyre_observations, calibrate_degradation
from app.simulation.models.tyre import get_standard_tyre_specs


class StrategyEvaluationResult(BaseModelLike := object):
    pass


try:
    from pydantic import BaseModel, Field

    class EvaluationOutput(BaseModel):
        candidate_id: str
        expected_race_time: float
        race_time_std: float
        expected_finish_position: float
        finish_position_std: float
        points_distribution: dict[str, float] | None = None
        pit_count: int = 1
        tyre_usage: dict[str, int] = Field(default_factory=dict)
        risk: float = 0.0
        uncertainty: float = 0.2
        evidence_tier: str = "PRIOR_ONLY"
        probability_of_gain: float = 0.5
        probability_of_loss: float = 0.5
        model_config = {"use_enum_values": True}

    class DecisionOutput(BaseModel):
        decision: str
        chosen_action: dict[str, Any]
        candidate_actions: list[dict[str, Any]]
        evaluations: list[dict[str, Any]]
        confidence: float
        uncertainty: float
        reasoning: list[str]
        components: list[str]
        evidence_tier: str
        constraints: dict[str, Any]
        provenance: dict[str, Any]
        model_config = {"use_enum_values": True}

except Exception:

    class EvaluationOutput:  # type: ignore
        pass

    class DecisionOutput:  # type: ignore
        pass

# Use pydantic directly
from pydantic import BaseModel, Field


class EvaluationOutput(BaseModel):
    candidate_id: str
    expected_race_time: float
    race_time_std: float
    expected_finish_position: float
    finish_position_std: float
    points_distribution: dict[str, float] | None = None
    pit_count: int = 1
    tyre_usage: dict[str, int] = Field(default_factory=dict)
    risk: float = 0.0
    uncertainty: float = 0.2
    evidence_tier: str = "PRIOR_ONLY"
    probability_of_gain: float = 0.5
    probability_of_loss: float = 0.5
    model_config = {"use_enum_values": True}


class DecisionOutput(BaseModel):
    decision: str
    target_compound: str | None = None
    pit_window: list[int] | None = None
    chosen_action: dict[str, Any]
    candidate_actions: list[dict[str, Any]]
    evaluations: list[dict[str, Any]]
    confidence: float
    uncertainty: float
    reasoning: list[str]
    components: list[str]
    evidence_tier: str
    constraints: dict[str, Any]
    provenance: dict[str, Any]
    model_config = {"use_enum_values": True}


class DecisionEngine:
    """First-class decision layer.

    API:
      DecisionEngine.decide(state, track_pit_loss, seed, sim_idx) -> DecisionOutput
      DecisionEngine.evaluate_strategy(baseline_state, candidate_strategy, scenario) -> EvaluationOutput  # noqa: E501
      DecisionEngine.compare_strategies(baseline_state, strategies, scenario) -> dict
    """

    def __init__(self, as_of: str | None = None, seed: int = 42, max_candidates: int = 8):
        self.as_of = as_of
        self.seed = seed
        self.candidate_gen = CandidateGenerator(as_of=as_of, max_candidates=max_candidates)
        self.pit_window_engine = PitWindowEngine(as_of=as_of)
        self.opponent_model = OpponentModel()
        self.explanation_engine = ExplanationEngine()
        # Load tyre calibration once (leakage-safe via as_of)
        self.tyre_specs = get_standard_tyre_specs()
        self.degradation_model: dict[str, Any] | None = None
        if as_of:
            try:
                obs = load_tyre_observations()
                self.degradation_model = calibrate_degradation(obs, as_of=as_of)
            except:
                self.degradation_model = None

    def _estimate_candidate_time(
        self, state: StrategyState, candidate: CandidateStrategy, track_pit_loss: float
    ) -> tuple[float, float, dict[str, Any]]:
        """Estimate expected race time for candidate via analytic + calibrated beta.

        Returns (mean, std, details)
        """
        # Degradation per compound
        def beta_for(compound: str) -> float:
            if self.degradation_model and compound.upper() in self.degradation_model:
                m = self.degradation_model[compound.upper()]
                if m.get("available"):
                    return float(m["beta"])
            # fallback to spec degradation_rate * 50? use 0.05 default
            try:
                spec = self.tyre_specs.get(compound) or self.tyre_specs.get(compound.lower()) or list(self.tyre_specs.values())[0]  # noqa: E501
                return float(getattr(spec, "degradation_rate", 0.02)) * 1.0
            except:
                return 0.05

        total = 0.0
        tyre_usage: dict[str, int] = {}
        risk = 0.0
        if not candidate.stints:
            # Continue / stay out: still has remaining laps on current compound
            laps = state.laps_remaining
            comp = state.current_compound
            beta = beta_for(comp)
            base = 90.0 * laps
            deg_sum = beta * laps * (laps - 1) / 2
            # Add degradation from current age offset
            # Current age contributes additional deg: beta * (current_age * laps + laps*(laps-1)/2) ??? simplified
            total += base + deg_sum + beta * state.tyre_age * laps
            tyre_usage[comp] = tyre_usage.get(comp, 0) + laps
            # risk
            try:
                optimal = int(2.5 / beta) if beta>0 else 25
            except:
                optimal = 25
            if state.tyre_age + laps > optimal * 1.3:
                risk += 8
            if state.tyre_age + laps > optimal * 1.6:
                risk += 15
        else:
            for stint in candidate.stints:
                comp = stint["compound"]
                laps = stint["laps"]
                beta = beta_for(comp)
                # stint time = base 90 per lap + degradation (beta*age sum) + fuel
                # sum_{age=0}^{laps-1} beta*age = beta * laps*(laps-1)/2
                deg_sum = beta * laps * (laps - 1) / 2
                base = 90.0 * laps
                total += base + deg_sum
                tyre_usage[comp] = tyre_usage.get(comp, 0) + laps
                # risk if laps > 1.3*optimal (optimal ~ 2.5/beta)
                try:
                    optimal = int(2.5 / beta) if beta>0 else 25
                except:
                    optimal = 25
                if laps > optimal * 1.3:
                    risk += 8
                if laps > optimal * 1.6:
                    risk += 15

        # Pit loss for each pit, adjusted for current RC phase
        pit_loss_per = track_pit_loss
        if state.race_control_phase == "SAFETY_CAR":
            pit_loss_per *= 0.35
        elif state.race_control_phase == "VSC":
            pit_loss_per *= 0.55
        total += pit_loss_per * len(candidate.pit_laps) if candidate.pit_laps else 0
        # Uncertainty: std grows with laps and risk
        std = 0.8 * len(candidate.stints) + 0.05 * state.laps_remaining + risk * 0.05
        # Weather uncertainty
        rain_prob = state.forecast_summary.get("rain_prob_next_5", 0) if state.forecast_summary else 0  # noqa: E501
        if rain_prob > 0.3:
            std += 1.5
            risk += 10
        # Evidence tier
        tier = "LIMITED" if self.degradation_model and any(self.degradation_model.get(c.upper(), {}).get("available") for c, _ in tyre_usage.items()) else "PRIOR_ONLY"  # noqa: E501
        return total, std, {"risk": min(risk, 100), "tyre_usage": tyre_usage, "evidence_tier": tier}

    def decide(
        self,
        state: StrategyState,
        track_pit_loss: float = 22.0,
        seed: int | None = None,
        sim_idx: int = 0,
    ) -> DecisionOutput:
        """Leakage-safe decision at lap t.

        Only uses state (current observable) + calibration priors via as_of.
        Isolated RNG stream 700.
        """
        s = seed if seed is not None else self.seed
        rng = strategy_rng(s, sim_idx, state.lap)

        candidates = self.candidate_gen.generate(state, track_pit_loss)
        if not candidates:
            # No candidate -> continue
            evals: list[EvaluationOutput] = []
            decision = "STAY_OUT"
            chosen = ContinueAction().model_dump()
            return DecisionOutput(
                decision=decision,
                target_compound=None,
                pit_window=None,
                chosen_action=chosen,
                candidate_actions=[],
                evaluations=[],
                confidence=0.5,
                uncertainty=0.5,
                reasoning=["no feasible candidates"],
                components=["UNCERTAINTY"],
                evidence_tier="PRIOR_ONLY",
                constraints={"max_candidates": self.candidate_gen.max_candidates},
                provenance={"seed": s, "sim_idx": sim_idx, "as_of": self.as_of, "rng_offset": 700},
            )

        # Evaluate each candidate via analytic mean/std
        evaluations: list[EvaluationOutput] = []
        for cand in candidates:
            mean, std, details = self._estimate_candidate_time(state, cand, track_pit_loss)
            # Opponent influence: undercut gain if gap <3s and candidate is early pit
            opp_gain = 0.0
            for opp in state.opponent_states:
                gap = float(opp.get("gap_ahead", 5.0))
                if gap > 0 and gap < 3.0 and cand.pit_laps and cand.pit_laps[0] <= state.lap + 3:
                    # Early pit gives undercut chance
                    opp_gain -= 0.6  # reduce expected time
            mean += opp_gain
            prob_gain = 0.5 + (evaluations[0].expected_race_time - mean) / 20.0 if evaluations else 0.5  # noqa: E501
            prob_gain = max(0.05, min(0.95, prob_gain))
            evaluations.append(
                EvaluationOutput(
                    candidate_id=cand.strategy_id,
                    expected_race_time=mean,
                    race_time_std=std,
                    expected_finish_position=state.position,  # placeholder; full MC would compute
                    finish_position_std=2.0,
                    pit_count=len(cand.pit_laps),
                    tyre_usage=details["tyre_usage"],
                    risk=details["risk"],
                    uncertainty=min(0.9, std / 20.0),
                    evidence_tier=details["evidence_tier"],
                    probability_of_gain=prob_gain,
                    probability_of_loss=1 - prob_gain,
                )
            )

        # Rank by expected_race_time + risk*0.1 (similar to existing evaluator)
        ranked = sorted(zip(candidates, evaluations), key=lambda x: x[1].expected_race_time + x[1].risk * 0.1)  # noqa: E501
        best_cand, best_eval = ranked[0]

        # Determine chosen action: PIT if best candidate has pit_lap == current lap or next
        # Our candidates have pit_laps relative to state.lap; if first pit_lap == state.lap+1 => PIT now/next
        pit_window = None
        decision = "STAY_OUT"
        target_compound = None
        if best_cand.pit_laps:
            # Use pit_window engine for precise window
            window = self.pit_window_engine.calculate(state, track_pit_loss)
            pit_window = [window.earliest_feasible_lap, window.latest_feasible_lap]
            first_pit = best_cand.pit_laps[0]
            if first_pit <= state.lap + 1:
                decision = "PIT"
                target_compound = best_cand.stints[1]["compound"] if len(best_cand.stints) > 1 else best_cand.stints[0]["compound"]  # noqa: E501
            elif first_pit <= state.lap + 3:
                decision = "PIT_NEXT_LAP"
            else:
                decision = "STAY_OUT"

        # Confidence from gap between best and second
        if len(ranked) >= 2:
            gap = ranked[1][1].expected_race_time - best_eval.expected_race_time
            confidence = min(0.95, 0.5 + gap / 10.0)
        else:
            confidence = 0.85

        # Explanation derived from inputs
        expl = self.explanation_engine.explain(state, best_cand, best_eval.model_dump(), window if 'window' in locals() else None)  # noqa: E501

        # Build chosen_action dict
        if decision == "PIT":
            chosen = PitAction(pit_lap=state.lap + 1, target_compound=target_compound or state.current_compound, expected_stint_length=best_cand.stints[1]["laps"] if len(best_cand.stints)>1 else None, reason=best_cand.reason, pit_window=pit_window, reasoning=expl["reasons"]).model_dump()  # noqa: E501
        elif decision == "PIT_NEXT_LAP":
            chosen = PitAction(pit_lap=state.lap + 2, target_compound=target_compound or state.current_compound, reason=best_cand.reason, pit_window=pit_window, reasoning=expl["reasons"]).model_dump()  # noqa: E501
        else:
            chosen = ContinueAction(reasoning=expl["reasons"]).model_dump()

        candidate_actions = [c.to_dict() for c in candidates]

        return DecisionOutput(
            decision=decision,
            target_compound=target_compound,
            pit_window=pit_window,
            chosen_action=chosen,
            candidate_actions=candidate_actions,
            evaluations=[e.model_dump() for _, e in ranked],
            confidence=confidence,
            uncertainty=best_eval.uncertainty,
            reasoning=expl["reasons"],
            components=expl["components"],
            evidence_tier=best_eval.evidence_tier,
            constraints={"max_candidates": self.candidate_gen.max_candidates, "laps_remaining": state.laps_remaining},  # noqa: E501
            provenance={"seed": s, "sim_idx": sim_idx, "as_of": self.as_of, "rng_offset": 700, "strategy_version": "strategy-v1.0.0"},  # noqa: E501
        )

    # --- Counterfactual API for Phase 21 ---
    def evaluate_strategy(
        self, baseline_state: StrategyState, candidate_strategy: CandidateStrategy | dict, track_pit_loss: float = 22.0  # noqa: E501
    ) -> EvaluationOutput:
        if isinstance(candidate_strategy, dict):
            cand = CandidateStrategy(
                strategy_id=candidate_strategy.get("strategy_id", "cand"),
                stints=candidate_strategy.get("stints", []),
                pit_laps=candidate_strategy.get("pit_laps", []),
                strategy_type=candidate_strategy.get("strategy_type", "one_stop"),
                reason=candidate_strategy.get("reason", ""),
            )
        else:
            cand = candidate_strategy
        mean, std, details = self._estimate_candidate_time(baseline_state, cand, track_pit_loss)
        return EvaluationOutput(
            candidate_id=cand.strategy_id,
            expected_race_time=mean,
            race_time_std=std,
            expected_finish_position=baseline_state.position,
            finish_position_std=2.0,
            pit_count=len(cand.pit_laps),
            tyre_usage=details["tyre_usage"],
            risk=details["risk"],
            uncertainty=min(0.9, std / 20.0),
            evidence_tier=details["evidence_tier"],
        )

    def compare_strategies(
        self, baseline_state: StrategyState, strategies: list[CandidateStrategy | dict], track_pit_loss: float = 22.0  # noqa: E501
    ) -> dict[str, Any]:
        evals = [self.evaluate_strategy(baseline_state, s, track_pit_loss) for s in strategies]
        if not evals:
            return {"deltas": []}
        base = evals[0]
        deltas = []
        for e in evals[1:]:
            deltas.append(
                {
                    "candidate_id": e.candidate_id,
                    "delta_expected_finish": e.expected_finish_position - base.expected_finish_position,  # noqa: E501
                    "delta_expected_race_time": e.expected_race_time - base.expected_race_time,
                    "delta_points": 0.0,  # would need points model
                    "delta_pit_count": e.pit_count - base.pit_count,
                    "p_gain": e.probability_of_gain,
                    "p_loss": e.probability_of_loss,
                    "uncertainty": e.uncertainty,
                    "evidence_tier": e.evidence_tier,
                }
            )
        return {"baseline": base.model_dump(), "evaluations": [e.model_dump() for e in evals], "deltas": deltas}  # noqa: E501
