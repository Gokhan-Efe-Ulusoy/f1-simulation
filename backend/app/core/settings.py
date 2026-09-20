from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "F1 Simulation"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database (for future use)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/f1sim"

    # Simulation
    DEFAULT_SEED: int | None = None
    SIMULATION_MODEL_VERSION: str = "0.1.0"

    # Phase 31 — job infrastructure (infrastructure only, no science change)
    JOB_QUEUE_BACKEND: str = "inprocess"
    REDIS_URL: str = "redis://localhost:6379/0"
    JOB_QUEUE_FALLBACK_INPROCESS: bool = True
    MAX_JOB_RUNTIME_SECONDS: int = 300
    JOB_HEARTBEAT_TIMEOUT_SECONDS: int = 60
    MONTECARLO_CHUNK_SIZE: int = 500
    JOB_INFRA_VERSION: str = "job-infrastructure-v1.0.0"
    MONTECARLO_EXEC_VERSION: str = "montecarlo-execution-v1.0.0"


settings = Settings()
