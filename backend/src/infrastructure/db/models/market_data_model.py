from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class MarketDataModel(Base):
    __tablename__ = "market_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spot_price_cop: Mapped[float] = mapped_column(Float, nullable=False)
    demand_mwh: Mapped[float] = mapped_column(Float, nullable=False)
    hydrology_pct: Mapped[float] = mapped_column(Float, nullable=False)
    reservoir_level_pct: Mapped[float] = mapped_column(Float, nullable=False)
    thermal_dispatch_pct: Mapped[float] = mapped_column(Float, nullable=False)
    agent_sic_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_market_data_timestamp", "timestamp"),
        Index("ix_market_data_agent_ts", "agent_sic_code", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<MarketDataModel {self.timestamp} price={self.spot_price_cop}>"
