"""Tyre engine — reference implementation, stateful, deterministic."""
from __future__ import annotations

from typing import Any
from app.simulation.tyre.state import TyreState
from app.simulation.tyre.compound import normalize_compound, CanonicalCompound
from app.simulation.tyre.tyre_era import tyre_era_for_season
from app.simulation.tyre.calibration import calibrate_degradation, calibrate_compound_effect, load_tyre_observations  # noqa: E501
import json
from pathlib import Path

class TyreEngine:
    """Reference tyre engine, easy to inspect as oracle."""

    def __init__(self, as_of: str = "2024-03-01"):
        self.as_of = as_of
        # Load calibration (leakage-safe: only < as_of)
        obs=load_tyre_observations()
        self.degradation_model=calibrate_degradation(obs, as_of=as_of)
        self.compound_model=calibrate_compound_effect(obs, as_of=as_of)
        # Warmup and cliff are NON_IDENTIFIABLE per audit
        self.warmup_available=False
        self.cliff_available=False

    def initialize(self, season: int, compound: str | None, tyre_age: int | None, stint_index: int = 0, start_lap: int | None = None) -> TyreState:  # noqa: E501
        era=tyre_era_for_season(season)
        if compound is None or tyre_age is None:
            return TyreState(
                compound=None,
                tyre_era=era,
                tyre_age=None,
                available=False,
                evidence_tier="PRIOR_ONLY" if era.value=="TYRE_ERA_PIRELLI" else "NON_IDENTIFIABLE",
            )
        canonical, source = normalize_compound(compound)
        # Check if compound era is identifiable
        comp_data=self.compound_model.get(canonical.value) if canonical else None
        if comp_data and not comp_data.get("available"):
            # Fall back to prior
            pass
        return TyreState(
            compound=canonical,
            source_compound=source,
            tyre_era=era,
            tyre_age=tyre_age,
            stint_index=stint_index,
            start_lap=start_lap,
            available=True,
            evidence_tier=comp_data.get("evidence_tier","LIMITED") if comp_data else "LIMITED",
        )

    def update(self, state: TyreState, lap: int, pit: bool = False, new_compound: str | None = None) -> TyreState:  # noqa: E501
        # If pit and new tyre, reset
        if pit and new_compound is not None:
            # New stint
            canonical, source = normalize_compound(new_compound)
            return TyreState(
                compound=canonical,
                source_compound=source,
                tyre_era=state.tyre_era,
                tyre_age=0,
                stint_index=state.stint_index+1,
                start_lap=lap,
                available=True,
                evidence_tier="OBSERVED" if canonical else "PRIOR_ONLY",
            )
        elif pit and new_compound is None:
            # Pit but unknown compound -> boundary available, compound null
            return TyreState(
                compound=None,
                tyre_era=state.tyre_era,
                tyre_age=None,
                stint_index=state.stint_index+1,
                start_lap=lap,
                available=False,
                evidence_tier="PRIOR_ONLY",
            )
        # Otherwise increment age if available
        if state.available and state.tyre_age is not None:
            new_age=state.tyre_age+1
            # Compute degradation and warmup
            deg=self._degradation_for(state, new_age)
            warm=self._warmup_for(state, new_age)
            return TyreState(
                compound=state.compound,
                source_compound=state.source_compound,
                tyre_era=state.tyre_era,
                tyre_age=new_age,
                stint_index=state.stint_index,
                start_lap=state.start_lap,
                grip=state.grip,  # simplified
                degradation=deg,
                warmup=warm,
                available=True,
                evidence_tier=state.evidence_tier,
            )
        else:
            return state

    def _degradation_for(self, state: TyreState, tyre_age: int) -> float:
        # Use calibrated beta for compound, else global, else prior 0.05
        if not state.available or state.compound is None:
            return 0.0
        comp_data=self.degradation_model.get(state.compound.value) or self.degradation_model.get("GLOBAL")  # noqa: E501
        if comp_data and comp_data.get("available"):
            beta=comp_data["beta"]
            return beta * tyre_age
        else:
            return 0.05 * tyre_age  # prior

    def _warmup_for(self, state: TyreState, tyre_age: int) -> float:
        # Only if identifiable, else 0
        if not self.warmup_available:
            return 0.0
        # Warmup penalty for first 2 laps
        if tyre_age <= 1:
            return 0.5
        elif tyre_age == 2:
            return 0.2
        else:
            return 0.0

    def performance_effect(self, state: TyreState) -> float:
        """Total tyre effect on lap time (seconds, positive = slower)."""
        if not state.available:
            return 0.0  # fallback to baseline, explicitly prior
        # Compound effect
        comp_effect=0.0
        if state.compound:
            comp_data=self.compound_model.get(state.compound.value)
            if comp_data and comp_data.get("available"):
                comp_effect=comp_data["effect"] or 0.0
        # Degradation
        deg=state.degradation
        # Warmup
        warm=state.warmup
        return comp_effect + deg + warm

    def uncertainty(self, state: TyreState) -> dict[str, Any]:
        if not state.available:
            return {"distribution": "Normal", "std": 1.0, "evidence_tier": "PRIOR_ONLY"}
        comp_data=self.degradation_model.get(state.compound.value) if state.compound else None
        if comp_data and comp_data.get("shrunk_std"):
            return {"distribution": "Normal", "std": comp_data["shrunk_std"], "evidence_tier": comp_data["evidence_tier"]}  # noqa: E501
        return {"distribution": "Normal", "std": 0.5, "evidence_tier": "LIMITED"}
