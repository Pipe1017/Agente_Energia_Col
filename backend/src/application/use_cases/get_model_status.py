"""
Use Cases: Model Status

- GetChampionStatus   → info del modelo champion actual
- ListModelVersions   → historial de versiones con métricas
"""
from __future__ import annotations

from ...domain.entities.model_version import ModelVersion, ModelStage
from ...domain.repositories.i_model_repository import IModelRepository


class GetChampionStatus:

    def __init__(self, model_repo: IModelRepository) -> None:
        self._repo = model_repo

    async def execute(self, task: str = "price_prediction_24h") -> ModelVersion | None:
        return await self._repo.get_champion(task=task)


class ListModelVersions:

    def __init__(self, model_repo: IModelRepository) -> None:
        self._repo = model_repo

    async def execute(
        self,
        task: str = "price_prediction_24h",
        stage: str | None = None,
    ) -> list[ModelVersion]:
        if stage:
            return await self._repo.get_by_stage(task=task, stage=ModelStage(stage))
        return await self._repo.get_all_by_task(task=task)
