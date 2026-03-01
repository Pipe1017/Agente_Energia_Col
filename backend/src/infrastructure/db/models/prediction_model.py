from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class PredictionModel(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_sic_code: Mapped[str] = mapped_column(String(8), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    hourly_predictions: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    actuals: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_predictions_agent_ts", "agent_sic_code", "generated_at"),
    )

    def __repr__(self) -> str:
        return f"<PredictionModel agent={self.agent_sic_code} at={self.generated_at}>"
