from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_sic_code: Mapped[str] = mapped_column(String(8), nullable=False)
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_factors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    hourly_offers: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    llm_model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="deepseek-chat")

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_recommendations_agent_ts", "agent_sic_code", "generated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RecommendationModel agent={self.agent_sic_code} "
            f"risk={self.risk_level} at={self.generated_at}>"
        )
