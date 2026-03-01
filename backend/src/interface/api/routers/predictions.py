from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import PredictionRepoDep
from ..schemas.prediction_schema import PricePredictionResponse, HourlyPriceResponse

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _hourly_to_response(hp) -> HourlyPriceResponse:
    return HourlyPriceResponse(
        target_hour=hp.target_hour,
        predicted_cop=hp.predicted_cop,
        lower_bound_cop=hp.lower_bound_cop,
        upper_bound_cop=hp.upper_bound_cop,
        confidence=hp.confidence,
        is_peak_hour=hp.is_peak_hour,
        spread_cop=hp.spread_cop,
    )


def _prediction_to_response(pred) -> PricePredictionResponse:
    peak = pred.peak_predictions
    return PricePredictionResponse(
        id=pred.id,
        agent_sic_code=pred.agent_sic_code,
        generated_at=pred.generated_at,
        model_version_id=pred.model_version_id,
        horizon_hours=pred.horizon_hours,
        overall_confidence=pred.overall_confidence,
        avg_predicted_price=pred.avg_predicted_price,
        max_predicted_price=pred.max_predicted_price.predicted_cop,
        min_predicted_price=pred.min_predicted_price.predicted_cop,
        hourly_predictions=[_hourly_to_response(h) for h in pred.hourly_predictions],
        peak_avg_price=(
            sum(h.predicted_cop for h in peak) / len(peak) if peak else pred.avg_predicted_price
        ),
    )


@router.get(
    "/latest",
    response_model=PricePredictionResponse,
    summary="Última predicción de precio 24h para un agente",
)
async def get_latest_prediction(
    repo: PredictionRepoDep,
    agent: Annotated[str, Query(description="SIC code del agente (ej. EPMC)")],
) -> PricePredictionResponse:
    """
    Retorna la predicción de precio más reciente para el agente indicado.
    La predicción incluye 24 horas hacia adelante con intervalos de confianza.
    """
    prediction = await repo.get_latest(agent.upper())
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sin predicciones disponibles para agente '{agent}'",
        )
    return _prediction_to_response(prediction)


@router.get(
    "/history",
    response_model=list[PricePredictionResponse],
    summary="Histórico de predicciones para un agente",
)
async def get_prediction_history(
    repo: PredictionRepoDep,
    agent: Annotated[str, Query(description="SIC code del agente")],
    start: Annotated[str, Query(description="Fecha inicio (ISO8601)")],
    end: Annotated[str, Query(description="Fecha fin (ISO8601)")],
) -> list[PricePredictionResponse]:
    from datetime import datetime
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start y end deben ser fechas ISO8601 válidas",
        )

    predictions = await repo.get_range(agent.upper(), start=start_dt, end=end_dt)
    return [_prediction_to_response(p) for p in predictions]
