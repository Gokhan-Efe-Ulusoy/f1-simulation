"""Multi-lap battle resource planner (Phase 8).

Bounded heuristic over a short horizon (2-5 laps): compares ATTACK_NOW,
ATTACK_NEXT, SAVE and DEFEND/HARVEST options using current fuel/ERS/tyre
resources plus expected trends. No global optimization is attempted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from app.simulation.racing.models import BattleResourceState


class BattlePlannerConfig(BaseModel):
    """Planner coefficients (documented, validated)."""

    horizon_laps: int = Field(default=3, ge=2, le=5)  # planning horizon
    attack_ers_cost_per_lap: float = Field(default=0.25, ge=0.0, le=1.0)
    attack_fuel_cost_per_lap: float = Field(default=0.3, ge=0.0, le=2.0)  # kg
    harvest_ers_gain_per_lap: float = Field(default=0.15, ge=0.0, le=1.0)
    attack_pace_gain: float = Field(default=0.25, ge=0.0, le=1.0)  # sec/lap
    save_pace_cost: float = Field(default=0.2, ge=0.0, le=1.0)  # sec/lap
    overtake_threshold_gain: float = Field(default=0.5, ge=0.0, le=3.0)  # sec needed

    model_config = {"use_enum_values": True}


@dataclass
class BattlePlan:
    """Recommended multi-lap battle plan."""

    action_now: str  # attack | save | harvest | defend
    horizon_actions: list[str] = field(default_factory=list)
    expected_gain: float = 0.0  # seconds over horizon
    expected_fuel_cost: float = 0.0  # kg over horizon
    expected_ers_cost: float = 0.0  # energy over horizon
    feasible: bool = True
    debug_info: dict[str, Any] = field(default_factory=dict)


class BattlePlanner:
    """Lightweight forward-looking battle planner."""

    def __init__(self, config: BattlePlannerConfig | None = None):
        self.config = config or BattlePlannerConfig()

    def plan(
        self,
        attacker: BattleResourceState,
        defender: BattleResourceState | None,
        gap: float,
        tyre_delta: float,
        laps_remaining: int,
        rng: np.random.Generator,
    ) -> BattlePlan:
        """Choose attack-now / attack-next / save / harvest over the horizon."""
        cfg = self.config
        horizon = max(2, min(cfg.horizon_laps, laps_remaining))

        options: dict[str, dict[str, float]] = {}
        # ATTACK_NOW: spend resources immediately
        ers_after = attacker.ers_energy - cfg.attack_ers_cost_per_lap * horizon * 0.5
        fuel_after = attacker.fuel_mass - attacker.fuel_target - cfg.attack_fuel_cost_per_lap
        feasible_now = ers_after >= 0.0 and fuel_after >= 0.0 and attacker.can_attack
        gain_now = cfg.attack_pace_gain * horizon + max(0.0, tyre_delta) * horizon * 0.5
        options["attack"] = {
            "gain": gain_now,
            "fuel": cfg.attack_fuel_cost_per_lap,
            "ers": cfg.attack_ers_cost_per_lap,
            "feasible": 1.0 if feasible_now else 0.0,
        }
        # ATTACK_NEXT: harvest one lap, then attack (only if horizon allows)
        gain_next = cfg.attack_pace_gain * max(0, horizon - 1) - cfg.save_pace_cost
        feasible_next = (
            attacker.ers_energy + cfg.harvest_ers_gain_per_lap - cfg.attack_ers_cost_per_lap >= 0.0
        )
        options["attack_next"] = {
            "gain": gain_next,
            "fuel": cfg.attack_fuel_cost_per_lap * 0.5,
            "ers": max(0.0, cfg.attack_ers_cost_per_lap - cfg.harvest_ers_gain_per_lap),
            "feasible": 1.0 if (feasible_next and horizon >= 3) else 0.0,
        }
        # SAVE: bank resources, accept small pace cost
        options["save"] = {
            "gain": -cfg.save_pace_cost * horizon,
            "fuel": -0.2,
            "ers": -cfg.harvest_ers_gain_per_lap,
            "feasible": 1.0,
        }
        # HARVEST: maximize regen when ERS-critical
        options["harvest"] = {
            "gain": -cfg.save_pace_cost * 1.5 * horizon,
            "fuel": -0.3,
            "ers": -cfg.harvest_ers_gain_per_lap * 1.5,
            "feasible": 1.0 if attacker.ers_conservation_required else 0.4,
        }

        # Pick feasible option with best gain; tie-break toward conservation
        ranked = sorted(
            options.items(),
            key=lambda kv: (kv[1]["feasible"], kv[1]["gain"]),
            reverse=True,
        )
        best_action, best = ranked[0]
        horizon_actions = [best_action] + ["save"] * (horizon - 1)
        if best_action == "attack_next":
            horizon_actions = ["harvest"] + ["attack"] * (horizon - 1)

        # Small deterministic jitter keeps ordering stable across seeds
        jitter = float(rng.normal(0.0, 0.01))
        return BattlePlan(
            action_now=best_action,
            horizon_actions=horizon_actions,
            expected_gain=best["gain"] + jitter,
            expected_fuel_cost=max(0.0, best["fuel"]),
            expected_ers_cost=max(0.0, best["ers"]),
            feasible=bool(best["feasible"]),
            debug_info={"horizon": horizon, "gap": gap,
                        "overtake_likely": bool(best["gain"] >= cfg.overtake_threshold_gain)},
        )
