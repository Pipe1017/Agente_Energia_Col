from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HourlyPriceResponse(BaseModel):
    target_hour: datetime
    predicted_cop: float = Field(description="Precio predicho central (COP/kWh)")
    lower_bound_cop: float = Field(description="Límite inferior intervalo 90% confianza")
    upper_bound_cop: float = Field(description="Límite superior intervalo 90% confianza")
    confidence: float = Field(ge=0.0, le=1.0)
    is_peak_hour: bool = Field(description="True para horas pico 18-21h")
    spread_cop: float = Field(description="Amplitud del intervalo (incertidumbre)")

    model_config = {"from_attributes": True}


class PricePredictionResponse(BaseModel):
    id: UUID
    agent_sic_code: str
    generated_at: datetime
    model_version_id: UUID
    horizon_hours: int
    overall_confidence: float
    avg_predicted_price: float
    max_predicted_price: float
    min_predicted_price: float
    hourly_predictions: list[HourlyPriceResponse]
    peak_avg_price: float = Field(description="Precio promedio en horas pico (18-21h)")

    model_config = {"from_attributes": True}


class PredictionSummaryResponse(BaseModel):
    """Vista compacta de predicción — para el dashboard ejecutivo."""
    generated_at: datetime
    avg_predicted_price: float
    peak_avg_price: float
    min_price: float
    max_price: float
    overall_confidence: float
    model_version: str
    horizon_hours: int
