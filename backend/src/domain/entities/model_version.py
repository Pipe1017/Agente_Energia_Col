from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ModelStage(str, Enum):
    DEV = "dev"               # recién entrenado, sin validar
    STAGING = "staging"       # en evaluación contra el champion
    PRODUCTION = "production" # champion activo en producción
    ARCHIVED = "archived"     # retirado


@dataclass
class ModelVersion:
    """
    Versión registrada de un modelo ML en el sistema.
    El champion es el único modelo en stage=PRODUCTION por tarea.
    Los challengers compiten en STAGING antes de ser promovidos.
    """

    id: UUID
    task: str                     # "price_prediction_24h", "demand_forecast"
    model_name: str               # "xgboost", "lstm", "prophet"
    version: str                  # "1.0.0", "1.1.0" (semver)
    stage: ModelStage
    artifact_path: str            # "models/price_prediction_24h/xgboost/1.0.0/"
    metrics: dict[str, float]     # {"rmse": 12.3, "mae": 8.1, "mape": 4.2}
    params: dict[str, Any]        # hiperparámetros del modelo
    is_champion: bool
    trained_at: datetime
    trained_on_days: int          # días de datos usados en entrenamiento

    promoted_at: datetime | None = None
    promoted_by: str | None = None  # "airflow_dag" o "user_manual"

    feature_schema: list[str] = field(default_factory=list)  # nombres de features

    def __post_init__(self) -> None:
        if not self.task:
            raise ValueError("task no puede estar vacío")
        if not self.model_name:
            raise ValueError("model_name no puede estar vacío")
        if not self.version:
            raise ValueError("version no puede estar vacío")
        if not self.artifact_path:
            raise ValueError("artifact_path no puede estar vacío")
        if self.is_champion and self.stage != ModelStage.PRODUCTION:
            raise ValueError("Solo los modelos en PRODUCTION pueden ser champion")

    @property
    def full_name(self) -> str:
        return f"{self.model_name}@{self.version}"

    @property
    def rmse(self) -> float | None:
        return self.metrics.get("rmse")

    @property
    def mae(self) -> float | None:
        return self.metrics.get("mae")

    @property
    def mape(self) -> float | None:
        return self.metrics.get("mape")

    def is_better_than(self, other: ModelVersion) -> bool:
        """Compara por RMSE (menor es mejor). Fallback a MAE."""
        if self.rmse is not None and other.rmse is not None:
            return self.rmse < other.rmse
        if self.mae is not None and other.mae is not None:
            return self.mae < other.mae
        return False
