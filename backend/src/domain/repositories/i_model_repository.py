from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.model_version import ModelStage, ModelVersion


class IModelRepository(ABC):

    @abstractmethod
    async def get_champion(self, task: str) -> ModelVersion | None:
        """Modelo activo en producción para la tarea dada."""
        ...

    @abstractmethod
    async def get_by_id(self, model_id: UUID) -> ModelVersion | None:
        ...

    @abstractmethod
    async def get_all_by_task(self, task: str) -> list[ModelVersion]:
        """Todos los modelos de una tarea, ordenados por trained_at DESC."""
        ...

    @abstractmethod
    async def get_by_stage(self, task: str, stage: ModelStage) -> list[ModelVersion]:
        ...

    @abstractmethod
    async def register(self, model: ModelVersion) -> ModelVersion:
        """Registra un nuevo modelo en stage DEV."""
        ...

    @abstractmethod
    async def promote(self, model_id: UUID) -> ModelVersion:
        """
        Promueve el modelo a PRODUCTION y archiva el champion anterior.
        Es una operación atómica (transacción).
        """
        ...

    @abstractmethod
    async def update_stage(self, model_id: UUID, stage: ModelStage) -> ModelVersion:
        ...
