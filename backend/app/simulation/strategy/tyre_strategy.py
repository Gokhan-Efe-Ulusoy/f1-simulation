"""Tyre Strategy — thin wrapper around calibrated degradation, leakage-safe."""
from __future__ import annotations

from typing import Any

from app.simulation.models.tyre import get_standard_tyre_specs
from app.simulation.tyre.calibration import load_tyre_observations, calibrate_degradation


class TyreStrategyEngine:
    def __init__(self, as_of: str | None = None):
        self.as_of = as_of
        self.specs = get_standard_tyre_specs()
        self.calibration: dict[str, Any] | None = None
        if as_of:
            try:
                obs = load_tyre_observations()
                self.calibration = calibrate_degradation(obs, as_of=as_of)
            except:
                self.calibration = None

    def beta_for(self, compound: str) -> tuple[float | None, str]:
        key = compound.upper()
        if self.calibration and key in self.calibration and self.calibration[key].get("available"):
            return float(self.calibration[key]["beta"]), self.calibration[key].get("evidence_tier", "CALIBRATED")  # noqa: E501
        # fallback to spec degradation_rate (PRIOR_ONLY)
        try:
            spec = self.specs.get(compound.lower()) or self.specs.get(compound) or list(self.specs.values())[0]  # noqa: E501
            return float(getattr(spec, "degradation_rate", 0.02)), "PRIOR_ONLY"
        except:
            return None, "NON_IDENTIFIABLE"
