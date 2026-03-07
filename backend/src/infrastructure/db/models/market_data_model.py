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
    # Precio de Escasez de Activación (CREG — varía mensualmente)
    precio_escasez_cop: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Generación real por tecnología (GWh/día — fuente SIMEM E17D25)
    gen_hidraulica_gwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    gen_termica_gwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    gen_solar_gwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    gen_eolica_gwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_sic_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_market_data_timestamp", "timestamp"),
        # Índice único NULLS NOT DISTINCT (PG 15+) para UPSERT idempotente
        # Creado manualmente con: CREATE UNIQUE INDEX ... NULLS NOT DISTINCT
        Index(
            "uq_market_data_ts_agent",
            "timestamp", "agent_sic_code",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<MarketDataModel {self.timestamp} price={self.spot_price_cop}>"
