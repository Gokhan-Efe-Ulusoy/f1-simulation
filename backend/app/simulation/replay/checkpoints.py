"""Phase 22 — Replay checkpoints (truncated-horizon legs).

A checkpoint is a replay of the same scenario truncated to `lap` laps (no
state is carried between checkpoints; each leg is an independent,
deterministic simulation from the same pre-race information). Only laps valid
for the actual race length are produced.
"""
from __future__ import annotations

CHECKPOINT_NAMES: tuple[str, ...] = (
    "pre_race", "formation",
    "lap_1", "lap_5", "lap_10", "lap_20", "lap_30", "lap_40", "lap_50",
    "finish",
)

_CHECKPOINT_LAPS: dict[str, int] = {
    "pre_race": 0,
    "formation": 0,
    "lap_1": 1,
    "lap_5": 5,
    "lap_10": 10,
    "lap_20": 20,
    "lap_30": 30,
    "lap_40": 40,
    "lap_50": 50,
}


def checkpoint_lap(name: str, total_laps: int) -> int:
    """Map a checkpoint name to a lap count for a race of `total_laps`."""
    if name == "finish":
        return int(total_laps)
    if name in _CHECKPOINT_LAPS:
        return int(_CHECKPOINT_LAPS[name])
    if name.startswith("lap_"):
        try:
            return max(1, int(name[4:]))
        except Exception:
            raise ValueError(f"unknown checkpoint {name!r}")
    raise ValueError(f"unknown checkpoint {name!r}")


def valid_checkpoints(total_laps: int | None) -> list[str]:
    """Checkpoint names valid for a race of `total_laps` (None -> default 58)."""
    total = int(total_laps) if total_laps else 58
    out = ["pre_race"]
    for name in CHECKPOINT_NAMES[2:-1]:
        if checkpoint_lap(name, total) < total:
            out.append(name)
    out.append("finish")
    return out
