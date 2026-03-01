from __future__ import annotations

import logging
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from ...config import get_settings
from ...domain.services.i_model_store import IModelStore

logger = logging.getLogger(__name__)


class MinioModelStore(IModelStore):
    """
    Almacenamiento de artefactos ML sobre MinIO (S3-compatible).
    Los modelos se guardan como:
      models/{task}/{model_name}/{version}/model.joblib
      models/{task}/{model_name}/{version}/metadata.json
      models/{task}/{model_name}/{version}/feature_schema.json
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET_MODELS

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Bucket creado: %s", self._bucket)

    async def upload(self, local_path: Path, destination: str) -> str:
        self._ensure_bucket()
        self._client.fput_object(
            bucket_name=self._bucket,
            object_name=destination,
            file_path=str(local_path),
        )
        full_path = f"{self._bucket}/{destination}"
        logger.info("Artefacto subido: %s", full_path)
        return full_path

    async def download(self, artifact_path: str, local_path: Path) -> None:
        # artifact_path puede incluir el bucket al inicio o no
        object_name = artifact_path.removeprefix(f"{self._bucket}/")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._client.fget_object(
            bucket_name=self._bucket,
            object_name=object_name,
            file_path=str(local_path),
        )
        logger.info("Artefacto descargado: %s → %s", artifact_path, local_path)

    async def exists(self, artifact_path: str) -> bool:
        object_name = artifact_path.removeprefix(f"{self._bucket}/")
        try:
            self._client.stat_object(self._bucket, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise

    async def delete(self, artifact_path: str) -> None:
        object_name = artifact_path.removeprefix(f"{self._bucket}/")
        self._client.remove_object(self._bucket, object_name)
        logger.info("Artefacto eliminado: %s", artifact_path)

    async def list_artifacts(self, prefix: str) -> list[str]:
        objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        return [f"{self._bucket}/{obj.object_name}" for obj in objects]
