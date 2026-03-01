from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.model_version import ModelStage, ModelVersion
from ....domain.repositories.i_model_repository import IModelRepository
from ..models.model_version_model import ModelVersionModel


class PgModelRepository(IModelRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: ModelVersionModel) -> ModelVersion:
        return ModelVersion(
            id=row.id,
            task=row.task,
            model_name=row.name,       # ORM column renamed: model_name → name
            version=row.version,
            stage=ModelStage(row.stage),
            artifact_path=row.artifact_path,
            metrics=dict(row.metrics or {}),
            params=dict(row.params or {}),
            is_champion=row.is_champion,
            trained_at=row.trained_at,
            trained_on_days=row.trained_on_days,
            promoted_at=row.promoted_at,
            promoted_by=row.promoted_by,
            feature_schema=list(row.feature_schema or []),
        )

    async def get_champion(self, task: str) -> ModelVersion | None:
        result = await self._session.execute(
            select(ModelVersionModel).where(
                ModelVersionModel.task == task,
                ModelVersionModel.is_champion.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_id(self, model_id: UUID) -> ModelVersion | None:
        row = await self._session.get(ModelVersionModel, model_id)
        return self._to_domain(row) if row else None

    async def get_all_by_task(self, task: str) -> list[ModelVersion]:
        result = await self._session.execute(
            select(ModelVersionModel)
            .where(ModelVersionModel.task == task)
            .order_by(ModelVersionModel.trained_at.desc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_stage(self, task: str, stage: ModelStage) -> list[ModelVersion]:
        result = await self._session.execute(
            select(ModelVersionModel).where(
                ModelVersionModel.task == task,
                ModelVersionModel.stage == stage.value,
            )
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def register(self, model: ModelVersion) -> ModelVersion:
        row = ModelVersionModel(
            id=model.id,
            task=model.task,
            name=model.model_name,      # ORM column renamed: model_name → name
            algorithm=model.model_name, # algorithm = implementación (igual a model_name)
            version=model.version,
            stage=model.stage.value,
            artifact_path=model.artifact_path,
            metrics=model.metrics,
            params=model.params,
            is_champion=model.is_champion,
            trained_at=model.trained_at,
            trained_on_days=model.trained_on_days,
            feature_schema=model.feature_schema,
        )
        self._session.add(row)
        await self._session.flush()
        return model

    async def promote(self, model_id: UUID) -> ModelVersion:
        """Promueve el modelo a PRODUCTION archivando el champion anterior. Atómico."""
        model_row = await self._session.get(ModelVersionModel, model_id)
        if not model_row:
            raise ValueError(f"Modelo no encontrado: {model_id}")

        # 1. Archivar champion actual
        await self._session.execute(
            update(ModelVersionModel)
            .where(
                ModelVersionModel.task == model_row.task,
                ModelVersionModel.is_champion.is_(True),
            )
            .values(stage=ModelStage.ARCHIVED.value, is_champion=False)
        )

        # 2. Promover el challenger
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(ModelVersionModel)
            .where(ModelVersionModel.id == model_id)
            .values(
                stage=ModelStage.PRODUCTION.value,
                is_champion=True,
                promoted_at=now,
                promoted_by="system",
            )
        )
        await self._session.flush()

        updated = await self._session.get(ModelVersionModel, model_id)
        return self._to_domain(updated)  # type: ignore[arg-type]

    async def update_stage(self, model_id: UUID, stage: ModelStage) -> ModelVersion:
        row = await self._session.get(ModelVersionModel, model_id)
        if not row:
            raise ValueError(f"Modelo no encontrado: {model_id}")
        row.stage = stage.value
        await self._session.flush()
        return self._to_domain(row)
