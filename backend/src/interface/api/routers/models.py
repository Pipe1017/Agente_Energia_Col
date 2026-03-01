from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import ModelRepoDep
from ..schemas.model_schema import ModelStatusResponse, ModelVersionResponse, ModelMetricsResponse
from ....application.use_cases.get_model_status import GetChampionStatus, ListModelVersions
from ....domain.entities.model_version import ModelVersion

router = APIRouter(prefix="/models", tags=["models"])


def _version_to_response(mv: ModelVersion) -> ModelVersionResponse:
    metrics = mv.metrics if isinstance(mv.metrics, dict) else {}
    return ModelVersionResponse(
        id=mv.id,
        name=mv.model_name,
        task=mv.task,
        algorithm=mv.model_name,   # domain entity no tiene 'algorithm' — usar model_name
        version=mv.version,
        stage=mv.stage.value,
        is_champion=mv.is_champion,
        metrics=ModelMetricsResponse(
            rmse=metrics.get("rmse"),
            mae=metrics.get("mae"),
            mape=metrics.get("mape"),
            r2=metrics.get("r2"),
            coverage_rate=metrics.get("coverage_rate"),
        ),
        trained_on_days=mv.trained_on_days,
        trained_at=mv.trained_at,
        promoted_at=mv.promoted_at,
    )


@router.get(
    "/champion",
    response_model=ModelStatusResponse,
    summary="Estado del modelo champion en producción",
)
async def get_champion(
    repo: ModelRepoDep,
    task: Annotated[str, Query()] = "price_prediction_24h",
) -> ModelStatusResponse:
    """
    Retorna información del modelo champion actual y cuántas versiones existen.
    """
    champion = await GetChampionStatus(repo).execute(task=task)
    all_versions = await ListModelVersions(repo).execute(task=task)

    last_training = max(
        (v.trained_at for v in all_versions), default=None
    ) if all_versions else None

    return ModelStatusResponse(
        has_champion=champion is not None,
        champion=_version_to_response(champion) if champion else None,
        total_versions=len(all_versions),
        last_training_at=last_training,
    )


@router.get(
    "/versions",
    response_model=list[ModelVersionResponse],
    summary="Historial de versiones de modelos",
)
async def list_versions(
    repo: ModelRepoDep,
    task: Annotated[str, Query()] = "price_prediction_24h",
    stage: Annotated[str | None, Query(
        description="Filtrar por stage: dev|staging|production|archived"
    )] = None,
) -> list[ModelVersionResponse]:
    valid_stages = {"dev", "staging", "production", "archived"}
    if stage and stage not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"stage inválido. Opciones: {valid_stages}",
        )
    versions = await ListModelVersions(repo).execute(task=task, stage=stage)
    return [_version_to_response(v) for v in versions]
