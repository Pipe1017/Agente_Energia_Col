from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class ModelVersionModel(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)            # ej. "xgboost"
    task: Mapped[str] = mapped_column(String(100), nullable=False)            # ej. "price_prediction_24h"
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)       # ej. "XGBoostPriceModel"
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="dev")

    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    feature_schema: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)

    is_champion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trained_on_days: Mapped[int] = mapped_column(Integer, nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_model_versions_task_stage", "task", "stage"),
        Index("ix_model_versions_champion", "task", "is_champion"),
    )

    def __repr__(self) -> str:
        return f"<ModelVersionModel {self.name}@{self.version} stage={self.stage}>"
