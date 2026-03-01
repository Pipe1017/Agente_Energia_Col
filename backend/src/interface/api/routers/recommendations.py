from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import AgentRepoDep, MarketRepoDep, PredictionRepoDep, RecommendationRepoDep, LLMServiceDep
from ..schemas.recommendation_schema import (
    GenerateRecommendationRequest,
    RecommendationResponse,
    HourlyOfferResponse,
)
from ....application.use_cases.get_recommendation import (
    GenerateRecommendation, GenerateRecommendationCommand,
    GetLatestRecommendation,
    ListRecommendations,
)
from ....domain.entities.recommendation import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _offer_to_response(o) -> HourlyOfferResponse:
    return HourlyOfferResponse(
        hour=o.hour,
        suggested_price_cop=o.suggested_price_cop,
        reasoning=o.reasoning,
        is_peak_hour=o.is_peak_hour,
    )


def _rec_to_response(rec: Recommendation) -> RecommendationResponse:
    return RecommendationResponse(
        id=rec.id,
        agent_sic_code=rec.agent_sic_code,
        generated_at=rec.generated_at,
        prediction_id=rec.prediction_id,
        narrative=rec.narrative,
        risk_level=rec.risk_level.value,
        key_factors=rec.key_factors,
        hourly_offers=[_offer_to_response(o) for o in rec.hourly_offers],
        llm_model_used=rec.llm_model_used,
        avg_suggested_price=rec.avg_suggested_price,
        summary=rec.summary,
    )


@router.get(
    "/latest",
    response_model=RecommendationResponse,
    summary="Última recomendación para un agente",
)
async def get_latest_recommendation(
    repo: RecommendationRepoDep,
    agent: Annotated[str, Query(description="SIC code del agente (ej. EPMC)")],
) -> RecommendationResponse:
    """
    Retorna la recomendación de oferta más reciente para el agente.
    Las recomendaciones son generadas automáticamente cada hora por el DAG llm_analysis.
    """
    rec = await GetLatestRecommendation(repo).execute(agent.upper())
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sin recomendaciones disponibles para agente '{agent}'",
        )
    return _rec_to_response(rec)


@router.get(
    "/history",
    response_model=list[RecommendationResponse],
    summary="Histórico de recomendaciones",
)
async def list_recommendations(
    repo: RecommendationRepoDep,
    agent: Annotated[str, Query(description="SIC code del agente")],
    start: Annotated[str, Query()],
    end: Annotated[str, Query()],
) -> list[RecommendationResponse]:
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fechas deben ser ISO8601 válidas",
        )
    recs = await ListRecommendations(repo).execute(agent.upper(), start=start_dt, end=end_dt)
    return [_rec_to_response(r) for r in recs]


@router.post(
    "/generate",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar recomendación on-demand (llama al LLM)",
)
async def generate_recommendation(
    body: GenerateRecommendationRequest,
    agent_repo: AgentRepoDep,
    market_repo: MarketRepoDep,
    prediction_repo: PredictionRepoDep,
    recommendation_repo: RecommendationRepoDep,
    llm: LLMServiceDep,
) -> RecommendationResponse:
    """
    Genera una nueva recomendación inmediatamente llamando al LLM (Deepseek).
    Útil para análisis ad-hoc fuera del ciclo horario automático.

    **Nota:** Este endpoint consume tokens de la API de Deepseek.
    """
    uc = GenerateRecommendation(
        agent_repo=agent_repo,
        market_repo=market_repo,
        prediction_repo=prediction_repo,
        recommendation_repo=recommendation_repo,
        llm_service=llm,
    )
    try:
        rec = await uc.execute(
            GenerateRecommendationCommand(
                sic_code=body.sic_code.upper(),
                context_hours=body.context_hours,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM no disponible: {exc}",
        )
    return _rec_to_response(rec)
