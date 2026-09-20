"""Candidate strategy generation — feasible, pruned, leakage-safe."""
from __future__ import annotations

from typing import Any
import numpy as np

from app.simulation.strategy.state import StrategyState
from app.simulation.strategy.pit_window import PitWindowEngine
from app.simulation.models.tyre import get_standard_tyre_specs
from app.simulation.models.strategy import StrategyType


class CandidateStrategy:
    """A candidate strategy — serializable."""

    def __init__(
        self,
        strategy_id: str,
        stints: list[dict[str, Any]],
        pit_laps: list[int],
        strategy_type: str,
        reason: str,
        evidence_tier: str = "PRIOR_ONLY",
    ):
        self.strategy_id = strategy_id
        self.stints = stints  # [{"compound": str, "laps": int}, ...]
        self.pit_laps = pit_laps
        self.strategy_type = strategy_type
        self.reason = reason
        self.evidence_tier = evidence_tier

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "stints": self.stints,
            "pit_laps": self.pit_laps,
            "strategy_type": self.strategy_type,
            "reason": self.reason,
            "evidence_tier": self.evidence_tier,
        }


class CandidateGenerator:
    """Generates feasible candidates respecting constraints, not brute-force all combos."""

    def __init__(self, as_of: str | None = None, max_candidates: int = 12):
        self.as_of = as_of
        self.max_candidates = max_candidates
        self.pit_window_engine = PitWindowEngine(as_of=as_of)

    def generate(
        self,
        state: StrategyState,
        track_pit_loss: float = 22.0,
        available_compounds: list[str] | None = None,
    ) -> list[CandidateStrategy]:
        candidates: list[CandidateStrategy] = []
        L_rem = state.laps_remaining
        if L_rem <= 0:
            return [CandidateStrategy("stay_out", [], [], "zero_stop", "no laps remaining")]

        if available_compounds is None:
            available_compounds = state.available_compounds or ["soft", "medium", "hard"]

        # Prune: realistic stop counts for remaining laps
        # e.g., <10 laps -> max 1 stop, <25 -> max 2, else 3
        if L_rem <= 10:
            max_stops = 1
        elif L_rem <= 35:
            max_stops = 2
        else:
            max_stops = 3

        # Use pit window to anchor preferred lap
        window = self.pit_window_engine.calculate(state, track_pit_loss)

        # Generate families
        # 1) Continue (no pit if outside window or tyre OK)
        if window.tyre_life_remaining > 8 and not window.reason.endswith("opportunity"):
            candidates.append(CandidateStrategy("continue", [], [], "zero_stop", "continue, tyre OK"))  # noqa: E501

        # 2) One-stop variants
        if max_stops >= 1:
            for compound in available_compounds:
                if compound == state.current_compound:
                    continue
                # Stint split: pit at preferred, early, late
                for pit_lap in {window.preferred_lap, window.earliest_feasible_lap, window.latest_feasible_lap}:  # noqa: E501
                    if pit_lap is None:
                        continue
                    # Clamp
                    if pit_lap < state.lap + 1 or pit_lap > state.lap + L_rem:
                        continue
                    first_laps = pit_lap - state.lap
                    second_laps = L_rem - first_laps
                    if first_laps < 3 or second_laps < 3:
                        continue
                    # Check tyre rules: must use at least 2 compounds (satisfied via compound != current)
                    sid = f"1stop_{compound}_{pit_lap}"
                    candidates.append(
                        CandidateStrategy(
                            sid,
                            [
                                {"compound": state.current_compound, "laps": first_laps},
                                {"compound": compound, "laps": second_laps},
                            ],
                            [pit_lap],
                            "one_stop",
                            f"1-stop to {compound} lap {pit_lap} ({window.reason})",
                        )
                    )

        # 3) Two-stop (if enough laps)
        if max_stops >= 2 and L_rem >= 20:
            # Early undercut vs late
            comps = [c for c in available_compounds if c != state.current_compound][:2]
            if len(comps) >= 1:
                c1 = comps[0]
                c2 = comps[1] if len(comps) > 1 else available_compounds[0]
                # Split remaining laps roughly 1/3 each
                l1 = L_rem // 3
                l2 = L_rem // 3
                l3 = L_rem - l1 - l2
                if min(l1, l2, l3) >= 5:
                    sid = f"2stop_{c1}_{c2}"
                    candidates.append(
                        CandidateStrategy(
                            sid,
                            [
                                {"compound": state.current_compound, "laps": l1},
                                {"compound": c1, "laps": l2},
                                {"compound": c2, "laps": l3},
                            ],
                            [state.lap + l1, state.lap + l1 + l2],
                            "two_stop",
                            f"2-stop balanced {c1}->{c2}",
                        )
                    )

        # 4) SC/VSC opportunity (if active, force pit now regardless of window)
        if state.race_control_phase in ("SAFETY_CAR", "VSC") and L_rem > 5:
            for compound in available_compounds:
                if compound == state.current_compound:
                    continue
                sid = f"sc_pit_{compound}_now"
                # Check not duplicate
                if any(c.strategy_id == sid for c in candidates):
                    continue
                candidates.append(
                    CandidateStrategy(
                        sid,
                        [
                            {"compound": state.current_compound, "laps": 1},
                            {"compound": compound, "laps": L_rem - 1},
                        ],
                        [state.lap + 1 if state.lap+1 <= state.lap+L_rem else state.lap],
                        "one_stop",
                        f"SC/VSC pit now to {compound}",
                    )
                )

        # 5) Weather crossover (if wetness high or forecast rain)
        rain_prob = state.forecast_summary.get("rain_prob_next_5", 0) if state.forecast_summary else 0  # noqa: E501
        if (state.wetness > 0.25 or rain_prob > 0.3) and "intermediate" in available_compounds:
            sid = "weather_crossover_inter"
            candidates.append(
                CandidateStrategy(
                    sid,
                    [{"compound": state.current_compound, "laps": 1}, {"compound": "intermediate", "laps": L_rem - 1}],  # noqa: E501
                    [state.lap + 1],
                    "one_stop",
                    "weather crossover to intermediate" + (f" wetness {state.wetness:.2f}" if state.wetness>0.25 else f" forecast {rain_prob:.2f}"),  # noqa: E501
                )
            )

        # Deduplicate and cap
        seen = set()
        uniq: list[CandidateStrategy] = []
        for c in candidates:
            if c.strategy_id not in seen:
                uniq.append(c)
                seen.add(c.strategy_id)
        return uniq[: self.max_candidates]
