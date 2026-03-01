"""
Registry de modelos ML para los DAGs de Airflow.

Responsabilidades:
  1. Guardar artefactos de modelo en MinIO
  2. Registrar versión en PostgreSQL via API REST del backend

Esta capa es SÍNCRONA — los DAGs de Airflow son síncronos.
"""
from __future__ import annotations

import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from minio import Minio

logger = logging.getLogger(__name__)

MODELS_BUCKET = "models"


class ModelRegistry:

    def __init__(
        self,
        minio_endpoint: str,
        minio_user: str,
        minio_password: str,
        minio_secure: bool = False,
    ) -> None:
        self._minio = Minio(
            minio_endpoint,
            access_key=minio_user,
            secret_key=minio_password,
            secure=minio_secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self._minio.bucket_exists(MODELS_BUCKET):
            self._minio.make_bucket(MODELS_BUCKET)

    # ------------------------------------------------------------------
    # Guardar modelo en MinIO
    # ------------------------------------------------------------------

    def save_model(
        self,
        model,                       # BaseEnergyModel instance
        metrics: dict[str, float],
        params: dict[str, Any],
        trained_on_days: int,
        version: str | None = None,
    ) -> str:
        """
        Guarda los artefactos del modelo en MinIO.

        Returns:
            artifact_path: ruta base en MinIO, ej:
              "models/price_prediction_24h/xgboost/1.0.0/"
        """
        version = version or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"{model.task}/{model.name}/{version}/"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Guardar artefactos del modelo localmente
            model.save(tmp_path)

            # Enriquecer metadata.json con métricas y trained_on_days
            metadata_path = tmp_path / "metadata.json"
            with open(metadata_path) as f:
                metadata = json.load(f)
            metadata["metrics"] = metrics
            metadata["params"] = params
            metadata["trained_on_days"] = trained_on_days
            metadata["trained_at"] = datetime.now(timezone.utc).isoformat()
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Subir todos los archivos a MinIO
            for file_path in tmp_path.iterdir():
                object_name = f"{prefix}{file_path.name}"
                self._minio.fput_object(MODELS_BUCKET, object_name, str(file_path))
                logger.info("Subido: %s/%s", MODELS_BUCKET, object_name)

        artifact_path = f"{MODELS_BUCKET}/{prefix}"
        logger.info("Modelo guardado en: %s", artifact_path)
        return artifact_path

    # ------------------------------------------------------------------
    # Cargar modelo desde MinIO
    # ------------------------------------------------------------------

    def load_model(self, model_class, artifact_path: str) -> Any:
        """
        Descarga artefactos desde MinIO y carga el modelo.

        artifact_path: "models/price_prediction_24h/xgboost/1.0.0/"
        """
        prefix = artifact_path.removeprefix(f"{MODELS_BUCKET}/")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Descargar todos los archivos del prefijo
            objects = self._minio.list_objects(MODELS_BUCKET, prefix=prefix, recursive=True)
            for obj in objects:
                filename = Path(obj.object_name).name
                local_file = tmp_path / filename
                self._minio.fget_object(MODELS_BUCKET, obj.object_name, str(local_file))

            return model_class.load(tmp_path)

    # ------------------------------------------------------------------
    # Listar versiones
    # ------------------------------------------------------------------

    def list_versions(self, task: str, model_name: str) -> list[str]:
        """Lista versiones disponibles en MinIO para task/model_name."""
        prefix = f"{task}/{model_name}/"
        objects = self._minio.list_objects(MODELS_BUCKET, prefix=prefix)
        versions = set()
        for obj in objects:
            parts = obj.object_name.split("/")
            if len(parts) >= 3:
                versions.add(parts[2])
        return sorted(versions)

    def get_metadata(self, artifact_path: str) -> dict:
        """Lee el metadata.json de un artefacto sin descargar el modelo."""
        prefix = artifact_path.removeprefix(f"{MODELS_BUCKET}/")
        object_name = f"{prefix}metadata.json"
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            self._minio.fget_object(MODELS_BUCKET, object_name, tmp.name)
            with open(tmp.name) as f:
                return json.load(f)
