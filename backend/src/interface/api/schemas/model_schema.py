from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ModelMetricsResponse(BaseModel):
    rmse: float | None = Field(None, description="Root Mean Square Error (COP/kWh)")
    mae: float | None = Field(None, description="Mean Absolute Error (COP/kWh)")
    mape: float | None = Field(None, description="Mean Absolute Percentage Error (%)")
    r2: float | None = Field(None, description="Coeficiente de determinación R²")
    coverage_rate: float | None = Field(None, description="Cobertura del intervalo de confianza")


class ModelVersionResponse(BaseModel):
    id: UUID
    name: str
    task: str
    algorithm: str
    version: str
    stage: str = Field(description="dev | staging | production | archived")
    is_champion: bool
    metrics: ModelMetricsResponse
    trained_on_days: int
    trained_at: datetime
    promoted_at: datetime | None = None

    model_config = {"from_attributes": True}


class ModelStatusResponse(BaseModel):
    """Estado del modelo champion en producción."""
    has_champion: bool
    champion: ModelVersionResponse | None = None
    total_versions: int
    last_training_at: datetime | None = None
