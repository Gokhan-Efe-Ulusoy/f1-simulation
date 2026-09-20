"""RaceEngine v2.0.0 — Setup & Vehicle Configuration Engine (Phase 20).

Extends v1.5.0 (strategy) with setup parameter integration:
  SetupState -> SetupEffects -> Adjusted Car -> LapTime -> Race Dynamics

Preserves all prior guarantees (temporal safety, RNG isolation, provenance).
"""
from __future__ import annotations

from typing import Any

from app.simulation.race_engine_v19 import StrategyAwareRaceEngine
from app.simulation.scenario_v14 import Scenario
from app.simulation.setup.models import (
    SetupState,
    SetupParameters,
    SetupMode,
    EvidenceTier,
    create_baseline_setup,
)
from app.simulation.setup.engine import SetupEngine
from app.simulation.setup.integration import SetupAwareLapTimeModel, create_setup_aware_inputs
from app.simulation.setup.validator import SetupValidator

RACEENGINE_VERSION = "raceengine-v2.0.0"
MODEL_VERSION = "0.7.0"
SETUP_MODEL_VERSION = "setup-v1.0.0"
CALIBRATION_VERSION = "calibration-v1.0.0"
DATASET_VERSION = "f1-dataset-v1.1"
WEATHER_MODEL_VERSION = "weather-v1.0.0"
WEATHER_CALIBRATION_VERSION = "weather-calibration-v1.0.0"
RACE_CONTROL_MODEL_VERSION = "racecontrol-v1.0.0"
RACE_CONTROL_POLICY_VERSION = "racecontrol-policy-v1.0.0"
STRATEGY_MODEL_VERSION = "strategy-v1.0.0"


class SetupAwareRaceEngine(StrategyAwareRaceEngine):
    """Setup-aware engine: adds vehicle configuration to StrategyAwareRaceEngine."""

    def __init__(
        self,
        calibration: str = CALIBRATION_VERSION,
        dataset: str = DATASET_VERSION,
        seed: int = 42,
        use_vectorized: bool = True,
        tyre_enabled: bool = True,
        weather_enabled: bool = True,
        race_control_enabled: bool = True,
        strategy_enabled: bool = True,
        setup_enabled: bool = True,
        setup_evidence_tier: EvidenceTier = EvidenceTier.PRIOR_ONLY,
    ):
        super().__init__(
            calibration=calibration,
            dataset=dataset,
            seed=seed,
            use_vectorized=use_vectorized,
            tyre_enabled=tyre_enabled,
            weather_enabled=weather_enabled,
            race_control_enabled=race_control_enabled,
            strategy_enabled=strategy_enabled,
        )
        self.version = RACEENGINE_VERSION
        self.model_version = MODEL_VERSION
        self.setup_enabled = setup_enabled
        self.setup_evidence_tier = setup_evidence_tier
        self._setup_engine = SetupEngine(evidence_tier=setup_evidence_tier)
        self._setup_validator = SetupValidator()
        self._lap_time_model = SetupAwareLapTimeModel(setup_evidence_tier=setup_evidence_tier)

    def _get_setup_for_driver(
        self,
        scenario: Scenario,
        driver_id: str,
        car: Any,
        track: Any,
    ) -> SetupState | None:
        """Get setup for a driver from scenario modifiers or use baseline."""
        if not self.setup_enabled:
            return None

        # Check scenario hypothetical_modifiers for setup
        mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
        setup_mods = mods.get("setup", {}) if isinstance(mods.get("setup"), dict) else {}

        # If setup explicitly disabled
        if setup_mods.get("enabled") is False:
            return None

        # If custom setup provided
        if "parameters" in setup_mods:
            setup_dict = setup_mods["parameters"]
            mode = SetupMode(setup_mods.get("mode", "hypothetical"))
            return create_setup_from_dict(
                setup_dict,
                car_id=getattr(car, "id", "default"),
                constructor_id=getattr(car, "team_id", "default"),
                season=scenario.season_id,
                track_id=scenario.circuit_id,
                mode=mode,
            )

        # Use baseline setup for this car/track
        return create_baseline_setup(
            car_id=getattr(car, "id", "default"),
            constructor_id=getattr(car, "team_id", "default"),
            season=scenario.season_id,
            track_id=scenario.circuit_id,
            mode=SetupMode.HISTORICAL if scenario.historical_mode else SetupMode.HYPOTHETICAL,
        )

    def _build_driver_setups(
        self,
        scenario: Scenario,
        drivers: list[Any],
        cars: dict[str, Any],
        track: Any,
    ) -> dict[str, SetupState]:
        """Build setup for each driver."""
        setups = {}
        for driver in drivers:
            driver_id = getattr(driver, "id", driver.get("driver_id") if isinstance(driver, dict) else "unknown")  # noqa: E501
            car = cars.get(driver_id) or cars.get(getattr(driver, "team_id", "default"))
            if car:
                setup = self._get_setup_for_driver(scenario, driver_id, car, track)
                if setup:
                    # Validate setup
                    validation = self._setup_validator.validate(setup)
                    if not validation.is_valid:
                        # Clamp to valid range
                        setup, _ = self._setup_validator.validate_and_clamp(setup)
                    setups[driver_id] = setup
        return setups

    def simulate(self, scenario: Scenario, simulations: int = 10000, seed: int | None = None) -> dict[str, Any]:  # noqa: E501
        if seed is None:
            seed = self.seed

        # Check setup enabled from scenario modifiers
        setup_enabled_local = self.setup_enabled
        try:
            mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
            setup_mods = mods.get("setup", {}) if isinstance(mods.get("setup"), dict) else {}
            if setup_mods.get("enabled") is False or mods.get("setup_enabled") is False:
                setup_enabled_local = False
            elif setup_mods.get("enabled") is True or mods.get("setup_enabled") is True:
                setup_enabled_local = True
        except:
            pass

        # Ensure scenario carries setup flag
        if not setup_enabled_local:
            if not hasattr(scenario, "hypothetical_modifiers") or scenario.hypothetical_modifiers is None:  # noqa: E501
                scenario.hypothetical_modifiers = {}
            if "setup" not in scenario.hypothetical_modifiers or not isinstance(scenario.hypothetical_modifiers["setup"], dict):  # noqa: E501
                scenario.hypothetical_modifiers["setup"] = {}
            scenario.hypothetical_modifiers["setup"]["enabled"] = False

        # Run parent simulation (which includes strategy, race control, weather, tyre;
        # vectorized path now applies per-driver setup offsets from scenario modifiers)
        result = super().simulate(scenario, simulations=simulations, seed=seed)

        # Surface real per-driver setup fingerprints/offsets (deterministic).
        try:
            from app.simulation.setup.offsets import (
                setup_fingerprints_for_scenario as _fps,
                setup_offsets_for_scenario as _offs,
                is_setup_enabled as _is_en,
            )
            fps = _fps(scenario) if setup_enabled_local else {}
            offs = _offs(scenario) if setup_enabled_local else {}
            resolved_enabled = bool(_is_en(scenario, self.setup_enabled)) and setup_enabled_local
        except Exception:
            fps, offs, resolved_enabled = {}, {}, setup_enabled_local

        # Add setup metadata to provenance
        result["provenance"]["setup_model_version"] = SETUP_MODEL_VERSION
        result["provenance"]["setup_enabled"] = resolved_enabled
        result["provenance"]["setup_evidence_tier"] = self.setup_evidence_tier.value
        if fps:
            result["provenance"]["setup_fingerprints"] = fps
        result["model_version"] = MODEL_VERSION

        # Add setup model info (merge with vectorized `setup` block if present)
        vec_setup = result.get("setup") if isinstance(result.get("setup"), dict) else {}
        result["setup_model"] = {
            "version": SETUP_MODEL_VERSION,
            "enabled": resolved_enabled,
            "evidence_tier": self.setup_evidence_tier.value,
            "offsets_sec_per_lap": offs,
            "fingerprints": fps,
            "vectorized": vec_setup,
        }
        # Keep top-level `setup` block consistent for fingerprint consumers
        if not isinstance(result.get("setup"), dict):
            result["setup"] = result["setup_model"]

        return result


# For backward compatibility during transition
RaceEngine = SetupAwareRaceEngine


# Helper to create setup from dict (moved here to avoid circular import)
def create_setup_from_dict(
    setup_dict: dict[str, float],
    car_id: str = "default",
    constructor_id: str = "default",
    season: str = "2024",
    track_id: str | None = None,
    mode: SetupMode = SetupMode.HYPOTHETICAL,
) -> SetupState:
    from app.simulation.setup.models import create_setup_from_dict as _create_setup
    return _create_setup(setup_dict, car_id, constructor_id, season, track_id, mode)
