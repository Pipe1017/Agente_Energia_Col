from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "energia_user"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "energia_col"

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """URL síncrona para Alembic (no soporta asyncpg)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # ------------------------------------------------------------------
    # MinIO
    # ------------------------------------------------------------------
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "changeme"
    MINIO_SECURE: bool = False

    # Nombres de buckets
    MINIO_BUCKET_RAW: str = "raw-data"
    MINIO_BUCKET_FEATURES: str = "features"
    MINIO_BUCKET_MODELS: str = "models"
    MINIO_BUCKET_REPORTS: str = "reports"

    # ------------------------------------------------------------------
    # LLM — proveedor configurable via LLM_PROVIDER
    # ------------------------------------------------------------------
    # Proveedor: "deepseek" (prod) | "ollama" (dev local) | "openai"
    LLM_PROVIDER: str = "deepseek"

    # Deepseek (compatible con protocolo OpenAI)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_MAX_TOKENS: int = 2048
    DEEPSEEK_TEMPERATURE: float = 0.3

    # Ollama (desarrollo local — sin API key)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # ------------------------------------------------------------------
    # MLflow
    # ------------------------------------------------------------------
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "price_prediction_24h"
    MLFLOW_REGISTERED_MODEL_NAME: str = "xgboost_price_predictor"

    # ------------------------------------------------------------------
    # Aplicación
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "info"
    DEBUG: bool = False

    # TTL de caché Redis en segundos
    CACHE_TTL_PREDICTION: int = 3600    # 1 hora
    CACHE_TTL_MARKET: int = 300         # 5 minutos
    CACHE_TTL_RECOMMENDATION: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
