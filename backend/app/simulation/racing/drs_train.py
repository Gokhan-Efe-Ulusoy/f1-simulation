from __future__ import annotations

from typing import Any

from app.simulation.racing.models import (
    DRSTrainConfig,
    DRSTrainContext,
    DRSTrainInfo,
)


class DRSTrainModel:
    """Detects and manages DRS trains.

    A DRS train occurs when multiple cars are within DRS range of each other
    but cannot easily overtake due to similar pace or defensive driving.
    """

    def __init__(
        self,
        config: DRSTrainConfig | None = None,
    ):
        self.config = config or DRSTrainConfig()

    def detect_train(
        self,
        context: DRSTrainContext,
    ) -> DRSTrainInfo:
        """Detect if a DRS train exists."""

        if not context.positions or len(context.positions) < self.config.min_train_length:
            return DRSTrainInfo(
                train_detected=False,
                leader_id=None,
                members=[],
                train_length=0,
                gaps=[],
                effective_overtake_opportunity=False,
                debug_info={"reason": "insufficient_cars"},
            )

        # Find consecutive cars within DRS range
        trains = []
        current_train = []

        for i, pos in enumerate(context.positions):
            driver_id = pos.get("driver_id", f"driver_{i}")
            gap_ahead = pos.get("gap_ahead", 0.0)

            if i == 0:
                # First car (leader)
                current_train = [driver_id]
            else:
                if gap_ahead <= self.config.max_train_gap:
                    current_train.append(driver_id)
                else:
                    # Gap too large, end current train
                    if len(current_train) >= self.config.min_train_length:
                        trains.append(current_train)
                    current_train = [driver_id]

        # Check last train
        if len(current_train) >= self.config.min_train_length:
            trains.append(current_train)

        if not trains:
            return DRSTrainInfo(
                train_detected=False,
                leader_id=None,
                members=[],
                train_length=0,
                gaps=[],
                effective_overtake_opportunity=False,
                debug_info={"reason": "no_train_detected"},
            )

        # Take the longest train (or first if equal)
        longest_train = max(trains, key=len)

        # Calculate gaps within train
        train_gaps = []
        for pos in context.positions:
            if pos.get("driver_id") in longest_train:
                gap = pos.get("gap_ahead", 0.0)
                train_gaps.append(gap)

        leader_id = longest_train[0]

        # Determine if there's an effective overtake opportunity
        # Train has opportunity if leader is significantly slower or has issues
        # For now, simple heuristic: train length > 3 reduces opportunity
        effective_opportunity = len(longest_train) <= 3

        debug_info = {
            "all_trains": trains,
            "longest_train_length": len(longest_train),
            "track_drs_zones": context.track_drs_zones,
            "max_train_gap_threshold": self.config.max_train_gap,
        }

        return DRSTrainInfo(
            train_detected=True,
            leader_id=leader_id,
            members=longest_train,
            train_length=len(longest_train),
            gaps=train_gaps,
            effective_overtake_opportunity=effective_opportunity,
            debug_info=debug_info,
        )

    def get_train_effects(
        self,
        train_info: DRSTrainInfo,
        is_leader: bool = False,
    ) -> dict[str, float]:
        """Get effects of being in a DRS train."""

        if not train_info.train_detected:
            return {
                "drs_effectiveness_multiplier": 1.0,
                "overtake_penalty": 0.0,
                "dirty_air_multiplier": 1.0,
            }

        if is_leader:
            # Leader gets clean air but no DRS
            return {
                "drs_effectiveness_multiplier": 0.0,
                "overtake_penalty": 0.0,
                "dirty_air_multiplier": 1.0,
            }

        # Train members get DRS but reduced effectiveness
        return {
            "drs_effectiveness_multiplier": self.config.train_drs_effectiveness_reduction,
            "overtake_penalty": self.config.train_overtake_penalty,
            "dirty_air_multiplier": 1.2,  # More dirty air in train
        }

    def get_debug_info(self, context: DRSTrainContext) -> dict[str, Any]:
        """Get detailed debug information."""
        train_info = self.detect_train(context)
        return {
            "input_positions": len(context.positions),
            "train_detected": train_info.train_detected,
            "train_length": train_info.train_length,
            "leader": train_info.leader_id,
            "members": train_info.members,
            "gaps": train_info.gaps,
            "effective_opportunity": train_info.effective_overtake_opportunity,
            "config": {
                "max_train_gap": self.config.max_train_gap,
                "min_train_length": self.config.min_train_length,
                "drs_effectiveness_reduction": self.config.train_drs_effectiveness_reduction,
            },
        }
