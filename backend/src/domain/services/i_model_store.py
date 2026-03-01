from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IModelStore(ABC):
    """
    Almacenamiento de artefactos ML (modelos, schemas, metadatos).
    Implementación actual: MinioModelStore.
    Interface compatible con cualquier object storage S3-like.
    """

    @abstractmethod
    async def upload(
        self,
        local_path: Path,
        destination: str,  # e.g. "models/price_prediction_24h/xgboost/1.0.0/model.joblib"
    ) -> str:
        """Sube un artefacto y retorna la ruta completa en el store."""
        ...

    @abstractmethod
    async def download(
        self,
        artifact_path: str,
        local_path: Path,
    ) -> None:
        """Descarga un artefacto al filesystem local."""
        ...

    @abstractmethod
    async def exists(self, artifact_path: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, artifact_path: str) -> None:
        ...

    @abstractmethod
    async def list_artifacts(self, prefix: str) -> list[str]:
        """Lista todas las rutas bajo un prefijo dado."""
        ...
