"""Vectorized tyre kernels for Phase 16 — NumPy/Numba, batch (N,D)."""
from __future__ import annotations

import numpy as np

try:
    import numba
    HAS_NUMBA=True
except ImportError:
    HAS_NUMBA=False

# Tyre state arrays: compound (int), age (int), stint (int), available (bool)
# We encode compound as int: 0=UNKNOWN, 1=SOFT,2=MEDIUM,3=HARD,4=INTER,5=WET

COMPOUND_MAP={"UNKNOWN":0,"SOFT":1,"MEDIUM":2,"HARD":3,"INTERMEDIATE":4,"WET":5}
INV_MAP={v:k for k,v in COMPOUND_MAP.items()}

def compound_to_int(compound: str | None) -> int:
    if compound is None:
        return 0
    return COMPOUND_MAP.get(compound, 0)

def int_to_compound(idx: int) -> str:
    return INV_MAP.get(idx, "UNKNOWN")

if HAS_NUMBA:
    @numba.njit
    def update_tyre_age_kernel(age: np.ndarray, available: np.ndarray, pit: np.ndarray) -> np.ndarray:  # noqa: E501
        # age: (N,D) int, pit: (N,D) bool
        N,D=age.shape
        out=np.empty_like(age)
        for i in range(N):
            for j in range(D):
                if pit[i,j]:
                    out[i,j]=0
                elif available[i,j]:
                    out[i,j]=age[i,j]+1
                else:
                    out[i,j]=age[i,j]
        return out

    @numba.njit
    def tyre_effect_kernel(compound: np.ndarray, age: np.ndarray, available: np.ndarray,
                           beta_soft: float, beta_medium: float, beta_hard: float) -> np.ndarray:
        N,D=compound.shape
        out=np.empty((N,D), dtype=np.float32)
        for i in range(N):
            for j in range(D):
                if not available[i,j]:
                    out[i,j]=0.0
                else:
                    c=compound[i,j]
                    a=age[i,j]
                    if c==1:  # SOFT
                        out[i,j]=beta_soft * a
                    elif c==2:  # MEDIUM
                        out[i,j]=beta_medium * a
                    elif c==3:  # HARD
                        out[i,j]=beta_hard * a
                    else:
                        out[i,j]=0.05 * a
        return out
else:
    def update_tyre_age_kernel(age, available, pit):
        out=age.copy()
        # pit resets to 0
        out[pit]=0
        # available increments
        mask=available & (~pit)
        out[mask] +=1
        return out

    def tyre_effect_kernel(compound, age, available, beta_soft, beta_medium, beta_hard):
        out=np.zeros_like(age, dtype=np.float32)
        # Use where
        soft_mask=(compound==1) & available
        medium_mask=(compound==2) & available
        hard_mask=(compound==3) & available
        out[soft_mask]=beta_soft * age[soft_mask]
        out[medium_mask]=beta_medium * age[medium_mask]
        out[hard_mask]=beta_hard * age[hard_mask]
        # fallback for unknown
        other_mask=available & ~(soft_mask|medium_mask|hard_mask)
        out[other_mask]=0.05 * age[other_mask]
        return out
