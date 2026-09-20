"""Vectorized weather kernels — NumPy/Numba, race-level (N, L) not per-driver.

Weather is shared across drivers: shape (N, L) or (N,).
No (N, D, L) duplication.

Provides Numba fast path + NumPy fallback, numerically equivalent within tolerance.
"""
from __future__ import annotations

import numpy as np

try:
    import numba

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


if HAS_NUMBA:

    @numba.njit
    def wetness_step_kernel(wetness: np.ndarray, rainfall: np.ndarray, drying_rates: np.ndarray) -> np.ndarray:  # noqa: E501
        # wetness (N,), rainfall (N,) mm/h, drying (N,)
        N = wetness.shape[0]
        out = np.empty_like(wetness)
        for i in range(N):
            r = rainfall[i]
            w = wetness[i]
            if r > 0:
                out[i] = w + r * 0.01
                if out[i] > 1.0:
                    out[i] = 1.0
            else:
                out[i] = w - drying_rates[i]
                if out[i] < 0.0:
                    out[i] = 0.0
        return out

    @numba.njit
    def grip_factor_kernel(wetness: np.ndarray) -> np.ndarray:
        N = wetness.shape[0]
        out = np.empty_like(wetness, dtype=np.float32)
        for i in range(N):
            w = wetness[i]
            if w <= 0.05:
                out[i] = 1.0
            elif w <= 0.2:
                out[i] = 0.95 - w * 0.2
            elif w <= 0.5:
                out[i] = 0.91 - (w - 0.2) * 0.4
            elif w <= 0.8:
                out[i] = 0.79 - (w - 0.5) * 0.5
            else:
                v = 0.64 - (w - 0.8) * 1.2
                out[i] = 0.4 if v < 0.4 else v
        return out

    @numba.njit
    def lap_weather_effect_kernel(grip: np.ndarray, temp_delta: np.ndarray) -> np.ndarray:
        # grip (N,) -> lap delta seconds (positive slower)
        N = grip.shape[0]
        out = np.empty_like(grip, dtype=np.float32)
        for i in range(N):
            g = grip[i]
            if g >= 0.99:
                out[i] = 0.0 + temp_delta[i] * 0.02  # tiny temp effect
            else:
                out[i] = (1.0 / g - 1.0) * 1.0 + temp_delta[i] * 0.01
        return out

else:

    def wetness_step_kernel(wetness, rainfall, drying_rates):
        out = wetness.copy()
        rain_mask = rainfall > 0
        out[rain_mask] = np.minimum(1.0, out[rain_mask] + rainfall[rain_mask] * 0.01)
        dry_mask = ~rain_mask
        out[dry_mask] = np.maximum(0.0, out[dry_mask] - drying_rates[dry_mask])
        return out

    def grip_factor_kernel(wetness):
        out = np.empty_like(wetness, dtype=np.float32)
        mask1 = wetness <= 0.05
        mask2 = (wetness > 0.05) & (wetness <= 0.2)
        mask3 = (wetness > 0.2) & (wetness <= 0.5)
        mask4 = (wetness > 0.5) & (wetness <= 0.8)
        mask5 = wetness > 0.8
        out[mask1] = 1.0
        out[mask2] = 0.95 - wetness[mask2] * 0.2
        out[mask3] = 0.91 - (wetness[mask3] - 0.2) * 0.4
        out[mask4] = 0.79 - (wetness[mask4] - 0.5) * 0.5
        out[mask5] = np.maximum(0.4, 0.64 - (wetness[mask5] - 0.8) * 1.2)
        return out

    def lap_weather_effect_kernel(grip, temp_delta):
        out = np.where(grip >= 0.99, temp_delta * 0.02, (1.0 / grip - 1.0) + temp_delta * 0.01)
        return out.astype(np.float32)
