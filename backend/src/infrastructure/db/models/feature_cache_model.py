from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class FeatureCacheModel(Base):
    """
    Cache de feature matrix calculada por feature_engineering_dag.
    Almacena features serializadas en JSONB para acceso rápido durante entrenamiento.
    """
    __tablename__ = "features_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, unique=True
    )
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_features_cache_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<FeatureCacheModel ts={self.timestamp} price={self.target_price}>"
