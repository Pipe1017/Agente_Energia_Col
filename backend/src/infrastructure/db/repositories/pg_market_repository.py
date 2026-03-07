from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.market_data import MarketSnapshot
from ....domain.repositories.i_market_repository import IMarketRepository
from ..models.market_data_model import MarketDataModel


class PgMarketRepository(IMarketRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: MarketDataModel) -> MarketSnapshot:
        # La BD almacena hydrology_pct como ratio (ej. 1.16 = 116%) y reservoir_level_pct
        # también como fracción (ej. 0.71 = 71%). Convertimos a porcentaje para el dominio.
        hydrology_pct = row.hydrology_pct * 100 if row.hydrology_pct <= 3.0 else row.hydrology_pct
        reservoir_pct = row.reservoir_level_pct * 100 if row.reservoir_level_pct <= 1.0 else row.reservoir_level_pct
        return MarketSnapshot(
            id=row.id,
            timestamp=row.timestamp,
            spot_price_cop=row.spot_price_cop,
            demand_mwh=row.demand_mwh,
            hydrology_pct=hydrology_pct,
            reservoir_level_pct=reservoir_pct,
            thermal_dispatch_pct=row.thermal_dispatch_pct,
            precio_escasez_cop=row.precio_escasez_cop,
            gen_hidraulica_gwh=row.gen_hidraulica_gwh,
            gen_termica_gwh=row.gen_termica_gwh,
            gen_solar_gwh=row.gen_solar_gwh,
            gen_eolica_gwh=row.gen_eolica_gwh,
            agent_sic_code=row.agent_sic_code,
            ingested_at=row.ingested_at,
        )

    async def get_latest(self, agent_sic_code: str | None = None) -> MarketSnapshot | None:
        stmt = select(MarketDataModel).order_by(MarketDataModel.timestamp.desc()).limit(1)
        if agent_sic_code:
            stmt = stmt.where(MarketDataModel.agent_sic_code == agent_sic_code.upper())
        else:
            stmt = stmt.where(MarketDataModel.agent_sic_code.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        # Si se pidió agente específico y no hay datos, caer al dato general del SIN
        if row is None and agent_sic_code:
            fallback = (
                select(MarketDataModel)
                .where(MarketDataModel.agent_sic_code.is_(None))
                .order_by(MarketDataModel.timestamp.desc())
                .limit(1)
            )
            result = await self._session.execute(fallback)
            row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_range(
        self,
        start: datetime,
        end: datetime,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        stmt = (
            select(MarketDataModel)
            .where(MarketDataModel.timestamp >= start, MarketDataModel.timestamp <= end)
            .order_by(MarketDataModel.timestamp.asc())
        )
        if agent_sic_code:
            stmt = stmt.where(MarketDataModel.agent_sic_code == agent_sic_code.upper())
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_last_n_hours(
        self,
        hours: int,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        # Usar el último timestamp disponible en BD como ancla (los datos XM tienen 2+ días de lag)
        latest_stmt = (
            select(func.max(MarketDataModel.timestamp))
            .where(MarketDataModel.agent_sic_code.is_(None))
        )
        result = await self._session.execute(latest_stmt)
        latest_ts = result.scalar_one_or_none()
        if latest_ts is None:
            return []
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        cutoff = latest_ts - timedelta(hours=hours)
        return await self.get_range(cutoff, latest_ts, agent_sic_code)

    async def bulk_insert(self, snapshots: list[MarketSnapshot]) -> int:
        rows = [
            MarketDataModel(
                id=s.id,
                timestamp=s.timestamp,
                spot_price_cop=s.spot_price_cop,
                demand_mwh=s.demand_mwh,
                hydrology_pct=s.hydrology_pct,
                reservoir_level_pct=s.reservoir_level_pct,
                thermal_dispatch_pct=s.thermal_dispatch_pct,
                agent_sic_code=s.agent_sic_code,
                ingested_at=s.ingested_at,
            )
            for s in snapshots
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return len(rows)

    async def get_average_price(self, start: datetime, end: datetime) -> float | None:
        result = await self._session.execute(
            select(func.avg(MarketDataModel.spot_price_cop)).where(
                MarketDataModel.timestamp >= start,
                MarketDataModel.timestamp <= end,
                MarketDataModel.agent_sic_code.is_(None),
            )
        )
        return result.scalar_one_or_none()
