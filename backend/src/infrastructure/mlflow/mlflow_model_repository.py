"""
MlflowModelRepository — implementa IModelRepository usando MLflow como
backend de tracking y registro de modelos.

MLflow almacena:
  - Experimentos y runs (parámetros, métricas, tags) → PostgreSQL
  - Artefactos del modelo                           → MinIO (S3-compatible)

Mapeo de stages:
  MLflow "Staging"    ↔  dominio ModelStage.DEV / STAGING
  MLflow "Production" ↔  dominio ModelStage.PRODUCTION
  MLflow "Archived"   ↔  dominio ModelStage.ARCHIVED

Nota: esta implementación es ASÍNCRONA (requiere anyio.to_thread.run_sync
porque mlflow.tracking.MlflowClient es síncrono).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

import anyio
import mlflow
from mlflow.tracking import MlflowClient

from ...domain.entities.model_version import ModelStage, ModelVersion
from ...domain.repositories.i_model_repository import IModelRepository

logger = logging.getLogger(__name__)

# Mapeo MLflow stage → dominio
_MLFLOW_TO_DOMAIN: dict[str, ModelStage] = {
    "Staging":    ModelStage.STAGING,
    "Production": ModelStage.PRODUCTION,
    "Archived":   ModelStage.ARCHIVED,
    "None":       ModelStage.DEV,
}

# Mapeo dominio → MLflow stage
_DOMAIN_TO_MLFLOW: dict[ModelStage, str] = {
    ModelStage.DEV:        "None",
    ModelStage.STAGING:    "Staging",
    ModelStage.PRODUCTION: "Production",
    ModelStage.ARCHIVED:   "Archived",
}


def _mv_to_domain(mv: mlflow.entities.model_registry.ModelVersion) -> ModelVersion:
    """Convierte un MLflow ModelVersion al dataclass de dominio."""
    tags = mv.tags or {}
    metrics_raw = {
        k.removeprefix("metric."): float(v)
        for k, v in tags.items()
        if k.startswith("metric.")
    }
    params_raw = {
        k.removeprefix("param."): v
        for k, v in tags.items()
        if k.startswith("param.")
    }

    stage = _MLFLOW_TO_DOMAIN.get(mv.current_stage, ModelStage.DEV)
    is_champion = mv.current_stage == "Production"

    promoted_at: datetime | None = None
    if is_champion and mv.last_updated_timestamp:
        promoted_at = datetime.fromtimestamp(
            mv.last_updated_timestamp / 1000, tz=timezone.utc
        )

    trained_at = datetime.fromtimestamp(
        mv.creation_timestamp / 1000, tz=timezone.utc
    ) if mv.creation_timestamp else datetime.now(timezone.utc)

    return ModelVersion(
        id=UUID(tags.get("domain_id", str(uuid.uuid4()))),
        task=tags.get("task", "price_prediction_24h"),
        model_name=mv.name,
        version=mv.version,
        stage=stage,
        artifact_path=mv.source or f"models:/{mv.name}/{mv.version}",
        metrics=metrics_raw,
        params=params_raw,
        is_champion=is_champion,
        trained_at=trained_at,
        trained_on_days=int(tags.get("trained_on_days", 90)),
        promoted_at=promoted_at,
        promoted_by=tags.get("promoted_by"),
    )


class MlflowModelRepository(IModelRepository):

    def __init__(self, tracking_uri: str, registered_model_name: str) -> None:
        self._tracking_uri = tracking_uri
        self._model_name = registered_model_name
        mlflow.set_tracking_uri(tracking_uri)
        self._client = MlflowClient(tracking_uri=tracking_uri)

    # ------------------------------------------------------------------
    # Helpers async (mlflow SDK es síncrono → run en threadpool)
    # ------------------------------------------------------------------

    async def _run_sync(self, fn, *args):
        return await anyio.to_thread.run_sync(lambda: fn(*args))

    # ------------------------------------------------------------------
    # IModelRepository
    # ------------------------------------------------------------------

    async def get_champion(self, task: str) -> ModelVersion | None:
        try:
            versions = await self._run_sync(
                self._client.get_latest_versions,
                self._model_name,
                ["Production"],
            )
            if not versions:
                return None
            # Filtrar por task tag si hay múltiples modelos
            for mv in versions:
                tags = mv.tags or {}
                if tags.get("task", task) == task:
                    return _mv_to_domain(mv)
            return _mv_to_domain(versions[0])
        except mlflow.exceptions.MlflowException:
            return None

    async def get_by_id(self, model_id: UUID) -> ModelVersion | None:
        try:
            all_versions = await self._run_sync(
                self._client.search_model_versions,
                f"name='{self._model_name}'",
            )
            for mv in all_versions:
                tags = mv.tags or {}
                if tags.get("domain_id") == str(model_id):
                    return _mv_to_domain(mv)
        except mlflow.exceptions.MlflowException:
            pass
        return None

    async def get_all_by_task(self, task: str) -> list[ModelVersion]:
        try:
            versions = await self._run_sync(
                self._client.search_model_versions,
                f"name='{self._model_name}'",
            )
            result = []
            for mv in versions:
                tags = mv.tags or {}
                if tags.get("task", task) == task:
                    result.append(_mv_to_domain(mv))
            return sorted(result, key=lambda m: m.trained_at, reverse=True)
        except mlflow.exceptions.MlflowException:
            return []

    async def get_by_stage(self, task: str, stage: ModelStage) -> list[ModelVersion]:
        mlflow_stage = _DOMAIN_TO_MLFLOW[stage]
        # "None" stage = DEV, not a valid MLflow filter stage
        if mlflow_stage == "None":
            all_versions = await self.get_all_by_task(task)
            return [v for v in all_versions if v.stage == stage]
        try:
            versions = await self._run_sync(
                self._client.get_latest_versions,
                self._model_name,
                [mlflow_stage],
            )
            result = []
            for mv in versions:
                tags = mv.tags or {}
                if tags.get("task", task) == task:
                    result.append(_mv_to_domain(mv))
            return result
        except mlflow.exceptions.MlflowException:
            return []

    async def register(self, model: ModelVersion) -> ModelVersion:
        domain_id = str(model.id)
        tags = {
            "domain_id": domain_id,
            "task": model.task,
            "trained_on_days": str(model.trained_on_days),
            **{f"metric.{k}": str(v) for k, v in model.metrics.items()},
            **{f"param.{k}": str(v) for k, v in model.params.items()},
        }

        def _register():
            mv = self._client.create_model_version(
                name=self._model_name,
                source=model.artifact_path,
                tags=tags,
            )
            return mv

        mv = await self._run_sync(_register)
        logger.info("Modelo registrado en MLflow: %s@%s", self._model_name, mv.version)
        return _mv_to_domain(mv)

    async def promote(self, model_id: UUID) -> ModelVersion:
        challenger = await self.get_by_id(model_id)
        if not challenger:
            raise ValueError(f"No existe modelo con id={model_id}")

        def _promote():
            # Archivar champion actual
            try:
                current = self._client.get_latest_versions(
                    self._model_name, ["Production"]
                )
                for mv in current:
                    self._client.transition_model_version_stage(
                        name=self._model_name,
                        version=mv.version,
                        stage="Archived",
                    )
            except mlflow.exceptions.MlflowException:
                pass

            # Promover challenger
            self._client.transition_model_version_stage(
                name=self._model_name,
                version=challenger.version,
                stage="Production",
            )
            self._client.set_model_version_tag(
                name=self._model_name,
                version=challenger.version,
                key="promoted_by",
                value="airflow_dag",
            )

        await self._run_sync(_promote)
        logger.info("Modelo promovido a Production: %s@%s", self._model_name, challenger.version)
        return await self.get_champion(challenger.task) or challenger

    async def update_stage(self, model_id: UUID, stage: ModelStage) -> ModelVersion:
        model = await self.get_by_id(model_id)
        if not model:
            raise ValueError(f"No existe modelo con id={model_id}")

        mlflow_stage = _DOMAIN_TO_MLFLOW[stage]
        if mlflow_stage == "None":
            mlflow_stage = "Staging"  # MLflow no soporta "None" en transition

        def _update():
            self._client.transition_model_version_stage(
                name=self._model_name,
                version=model.version,
                stage=mlflow_stage,
            )

        await self._run_sync(_update)
        return await self.get_by_id(model_id) or model
