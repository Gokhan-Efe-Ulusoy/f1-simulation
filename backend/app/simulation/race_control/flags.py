"""Sector-level flag state."""
from __future__ import annotations

import numpy as np

from app.simulation.race_control.models import SectorControlState


def init_sector_flags(n_sims: int, n_laps: int, n_sectors: int = 3) -> np.ndarray:
    """Allocate (N, L, S) sector flags: 0=GREEN, 1=YELLOW, 2=DOUBLE_YELLOW."""
    return np.zeros((n_sims, n_laps, n_sectors), dtype=np.int8)


def set_yellow(sector_flags: np.ndarray, sim_idx: int, lap_idx: int, sector: int, double: bool = False) -> None:  # noqa: E501
    val = 2 if double else 1
    sector_flags[sim_idx, lap_idx, sector] = val


def clear_sector_yellows(sector_flags: np.ndarray, sim_idx: int, lap_idx: int) -> None:
    sector_flags[sim_idx, lap_idx, :] = 0


def is_yellow_affected(sector_flags: np.ndarray, sim_idx: int, lap_idx: int, sector: int) -> bool:
    return sector_flags[sim_idx, lap_idx, sector] != 0


def sector_state_for(sector_flags: np.ndarray, sim_idx: int, lap_idx: int) -> list[SectorControlState]:  # noqa: E501
    mapping = {0: SectorControlState.GREEN, 1: SectorControlState.YELLOW, 2: SectorControlState.DOUBLE_YELLOW}  # noqa: E501
    return [mapping[int(v)] for v in sector_flags[sim_idx, lap_idx, :]]
