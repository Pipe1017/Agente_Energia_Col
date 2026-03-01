from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HourlyOfferResponse(BaseModel):
    hour: datetime
    suggested_price_cop: float = Field(description="Precio de oferta sugerido (COP/kWh)")
    reasoning: str = Field(description="Justificación del LLM para esta hora")
    is_peak_hour: bool

    model_config = {"from_attributes": True}


class RecommendationResponse(BaseModel):
    id: UUID
    agent_sic_code: str
    generated_at: datetime
    prediction_id: UUID
    narrative: str = Field(description="Análisis narrativo completo del LLM")
    risk_level: str = Field(description="low | medium | high")
    key_factors: list[str] = Field(description="Factores clave que influyen la recomendación")
    hourly_offers: list[HourlyOfferResponse]
    llm_model_used: str
    # Campos calculados
    avg_suggested_price: float
    summary: str = Field(description="Resumen de una línea para la vista ejecutiva")

    model_config = {"from_attributes": True}


class RecommendationSummaryResponse(BaseModel):
    """Vista compacta — dashboard ejecutivo."""
    generated_at: datetime
    risk_level: str
    avg_suggested_price: float
    summary: str
    key_factors: list[str]


class GenerateRecommendationRequest(BaseModel):
    sic_code: str = Field(..., min_length=2, max_length=8, examples=["EPMC"])
    context_hours: int = Field(
        72, ge=24, le=168,
        description="Horas de contexto histórico para el LLM (24-168h)"
    )
