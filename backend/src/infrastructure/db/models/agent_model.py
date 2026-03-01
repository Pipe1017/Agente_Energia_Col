from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sic_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    resources: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    installed_capacity_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    variable_cost_cop_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AgentModel {self.name} ({self.sic_code})>"
