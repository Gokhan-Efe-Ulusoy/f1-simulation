"""Vectorized kernels for race control — gap compression, pace control, DRS gating."""
from __future__ import annotations

import numpy as np

try:
    import numba

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

# Phase integer encoding for fast kernels
# Must align with models.RaceControlState but assign stable ints for arrays
PHASE_GREEN = 0
PHASE_YELLOW = 1
PHASE_DOUBLE_YELLOW = 2
PHASE_VSC = 3
PHASE_SAFETY_CAR = 4
PHASE_RED_FLAG = 5
PHASE_FORMATION_LAP = 6
PHASE_START = 7
PHASE_RESTART = 8
PHASE_CHEQUERED_FLAG = 9
PHASE_RACE_SUSPENDED = 10
PHASE_RACE_RESUMED = 11

# Mapping from string to int for convenience
PHASE_MAP = {
    "GREEN": PHASE_GREEN,
    "YELLOW": PHASE_YELLOW,
    "DOUBLE_YELLOW": PHASE_DOUBLE_YELLOW,
    "VSC": PHASE_VSC,
    "SAFETY_CAR": PHASE_SAFETY_CAR,
    "RED_FLAG": PHASE_RED_FLAG,
    "FORMATION_LAP": PHASE_FORMATION_LAP,
    "START": PHASE_START,
    "RESTART": PHASE_RESTART,
    "CHEQUERED_FLAG": PHASE_CHEQUERED_FLAG,
    "RACE_SUSPENDED": PHASE_RACE_SUSPENDED,
    "RACE_RESUMED": PHASE_RACE_RESUMED,
}


if HAS_NUMBA:

    @numba.njit
    def gaps_compression_kernel(times: np.ndarray, race_phase: np.ndarray, target_gap: float = 0.7, rate_sc: float = 0.55, rate_vsc: float = 0.25) -> np.ndarray:  # noqa: E501
        """In-place gap compression on times matrix (N,D).

        race_phase (N,) int: SC/VSC indication.
        We adjust times to shrink gaps toward target.
        Leader unchanged per sim (minimum time).
        """
        N, D = times.shape
        for n in range(N):
            phase = race_phase[n]
            if phase == PHASE_SAFETY_CAR:
                r = rate_sc
            elif phase == PHASE_VSC:
                r = rate_vsc
            elif phase == PHASE_YELLOW or phase == PHASE_DOUBLE_YELLOW:
                r = 0.08
            else:
                continue
            # Find leader time
            min_t = times[n, 0]
            for d in range(1, D):
                if times[n, d] < min_t:
                    min_t = times[n, d]
            for d in range(D):
                gap = times[n, d] - min_t
                if gap <= 1e-6:
                    continue
                new_gap = gap * (1 - r) + target_gap * r
                # Preserve order: no gap inversion — clamp to previous driver's gap? For now keep simple.
                times[n, d] = min_t + new_gap
        return times

    @numba.njit
    def pace_control_kernel(lap_times: np.ndarray, race_phase: np.ndarray, ref_time: float = 90.0) -> np.ndarray:  # noqa: E501
        """Apply SC/VSC pace control: lap time floored to controlled pace."""
        N, D = lap_times.shape
        for n in range(N):
            phase = race_phase[n]
            if phase == PHASE_SAFETY_CAR:
                floor = ref_time * 1.35
                for d in range(D):
                    if lap_times[n, d] < floor:
                        lap_times[n, d] = floor + np.random.normal(0, 0.15) if False else floor
            elif phase == PHASE_VSC:
                floor = ref_time * 1.25
                for d in range(D):
                    if lap_times[n, d] < floor:
                        lap_times[n, d] = floor
            elif phase == PHASE_YELLOW:
                floor = ref_time * 1.12
                for d in range(D):
                    if lap_times[n, d] < floor:
                        lap_times[n, d] = floor
            elif phase == PHASE_RED_FLAG or phase == PHASE_RACE_SUSPENDED:
                # Frozen: lap times 0 (no progression)
                for d in range(D):
                    lap_times[n, d] = 0.0
        return lap_times

    @numba.njit
    def overtake_mask_kernel(race_phase: np.ndarray) -> np.ndarray:
        """Returns (N,) mask where overtaking / battles allowed (1) or suppressed (0)."""
        N = race_phase.shape[0]
        out = np.empty(N, dtype=np.int8)
        for n in range(N):
            p = race_phase[n]
            if p == PHASE_GREEN or p == PHASE_RESTART or p == PHASE_RACE_RESUMED:
                out[n] = 1
            elif p == PHASE_YELLOW and False:
                out[n] = 0
            else:
                # YELLOW, VSC, SC, RED_FLAG suppress
                if p == PHASE_YELLOW:
                    out[n] = 0  # suppressed, but spec says reduced not zero — treat as 0 for deterministic no-teleport  # noqa: E501
                else:
                    out[n] = 0 if (p == PHASE_VSC or p == PHASE_SAFETY_CAR or p == PHASE_RED_FLAG or p == PHASE_RACE_SUSPENDED) else 1  # noqa: E501
                if p == PHASE_GREEN:
                    out[n] = 1
        return out

else:

    def gaps_compression_kernel(times, race_phase, target_gap=0.7, rate_sc=0.55, rate_vsc=0.25):
        N, D = times.shape
        for n in range(N):
            phase = int(race_phase[n])
            if phase == PHASE_SAFETY_CAR:
                r = rate_sc
            elif phase == PHASE_VSC:
                r = rate_vsc
            elif phase in (PHASE_YELLOW, PHASE_DOUBLE_YELLOW):
                r = 0.08
            else:
                continue
            min_t = np.min(times[n])
            gaps = times[n] - min_t
            mask_leader = gaps <= 1e-6
            new_gaps = gaps * (1 - r) + target_gap * r
            new_gaps[mask_leader] = 0.0
            times[n] = min_t + new_gaps
        return times

    def pace_control_kernel(lap_times, race_phase, ref_time=90.0):
        for n in range(len(race_phase)):
            phase = int(race_phase[n])
            if phase == PHASE_SAFETY_CAR:
                floor = ref_time * 1.35
                mask = lap_times[n] < floor
                lap_times[n, mask] = floor
            elif phase == PHASE_VSC:
                floor = ref_time * 1.25
                mask = lap_times[n] < floor
                lap_times[n, mask] = floor
            elif phase == PHASE_YELLOW:
                floor = ref_time * 1.12
                mask = lap_times[n] < floor
                lap_times[n, mask] = floor
            elif phase in (PHASE_RED_FLAG, PHASE_RACE_SUSPENDED, PHASE_CHEQUERED_FLAG):
                lap_times[n, :] = 0.0
        return lap_times

    def overtake_mask_kernel(race_phase):
        out = np.zeros(len(race_phase), dtype=np.int8)
        for n, p in enumerate(race_phase):
            p = int(p)
            if p in (PHASE_GREEN, PHASE_RESTART, PHASE_RACE_RESUMED):
                out[n] = 1
            elif p in (PHASE_VSC, PHASE_SAFETY_CAR, PHASE_RED_FLAG, PHASE_RACE_SUSPENDED, PHASE_YELLOW, PHASE_DOUBLE_YELLOW, PHASE_CHEQUERED_FLAG):  # noqa: E501
                out[n] = 0
            else:
                out[n] = 1
        return out


def drs_mask_for_phase(race_phase_arr: np.ndarray) -> np.ndarray:
    """DRS enabled only GREEN; restart pending disables for 2 laps."""
    # race_phase_arr (N, L) int
    # Returns bool array same shape where DRS allowed
    drs = race_phase_arr == PHASE_GREEN
    # After RESTART, DRS disabled for next 2 laps (FIA-like prior)
    N, L = race_phase_arr.shape
    for n in range(N):
        restart_laps = np.where(race_phase_arr[n] == PHASE_RESTART)[0]
        for rl in restart_laps:
            for dl in range(1, 3):
                if rl + dl < L:
                    drs[n, rl + dl] = False
    return drs
