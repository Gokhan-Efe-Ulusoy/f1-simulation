from app.core.settings import settings

__all__ = ["settings", "simulation_config", "SimulationConfig"]


class SimulationConfig:
    """Base configuration for the simulation engine."""

    # Version of the simulation model
    model_version: str = settings.SIMULATION_MODEL_VERSION

    # Random seed for reproducibility
    seed: int | None = settings.DEFAULT_SEED


# Global simulation config instance
simulation_config = SimulationConfig()
