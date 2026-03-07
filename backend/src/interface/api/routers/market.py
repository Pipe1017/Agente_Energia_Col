from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import MarketRepoDep
from ..schemas.market_schema import (
    MarketHistoryResponse,
    MarketSnapshotResponse,
    MarketSummaryResponse,
)
from ....application.use_cases.get_market_snapshot import (
    GetMarketLastNHours,
    GetMarketSnapshot,
    GetMarketHistory,
)
from ....domain.entities.market_data import MarketSnapshot

router = APIRouter(prefix="/market", tags=["market"])


def _snapshot_to_response(s: MarketSnapshot) -> MarketSnapshotResponse:
    return MarketSnapshotResponse(
        timestamp=s.timestamp,
        spot_price_cop=s.spot_price_cop,
        demand_mwh=s.demand_mwh,
        hydrology_pct=s.hydrology_pct,
        reservoir_level_pct=s.reservoir_level_pct,
        thermal_dispatch_pct=s.thermal_dispatch_pct,
        agent_sic_code=s.agent_sic_code,
        precio_escasez_cop=s.precio_escasez_cop,
        gen_hidraulica_gwh=s.gen_hidraulica_gwh,
        gen_termica_gwh=s.gen_termica_gwh,
        gen_solar_gwh=s.gen_solar_gwh,
        gen_eolica_gwh=s.gen_eolica_gwh,
        hydrology_status=s.hydrology_status,
        is_hydrology_critical=s.is_hydrology_critical,
        is_reservoir_low=s.is_reservoir_low,
    )


@router.get("/latest", response_model=MarketSnapshotResponse, summary="Último snapshot de mercado")
async def get_latest_market(
    repo: MarketRepoDep,
    agent: Annotated[str | None, Query(description="SIC del agente (omitir para dato SIN general)")] = None,
) -> MarketSnapshotResponse:
    """
    Retorna el snapshot más reciente del mercado eléctrico colombiano.
    Si `agent` se omite retorna el dato general del SIN.
    """
    result = await GetMarketSnapshot(repo).execute(agent_sic_code=agent)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay datos de mercado disponibles",
        )
    return _snapshot_to_response(result.snapshot)


@router.get(
    "/history",
    response_model=MarketHistoryResponse,
    summary="Histórico de mercado por rango de fechas",
)
async def get_market_history(
    repo: MarketRepoDep,
    start: Annotated[datetime, Query(description="Fecha inicio ISO8601")],
    end: Annotated[datetime, Query(description="Fecha fin ISO8601")],
    agent: Annotated[str | None, Query()] = None,
) -> MarketHistoryResponse:
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end debe ser mayor que start",
        )
    snapshots = await GetMarketHistory(repo).execute(start, end, agent_sic_code=agent)
    return MarketHistoryResponse(
        agent_sic_code=agent,
        start=start,
        end=end,
        count=len(snapshots),
        snapshots=[_snapshot_to_response(s) for s in snapshots],
    )


@router.get(
    "/last/{hours}h",
    response_model=list[MarketSnapshotResponse],
    summary="Últimas N horas de datos de mercado",
)
async def get_last_n_hours(
    hours: int,
    repo: MarketRepoDep,
    agent: Annotated[str | None, Query()] = None,
) -> list[MarketSnapshotResponse]:
    if not (1 <= hours <= 2160):  # hasta 90 días
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="hours debe estar entre 1 y 2160",
        )
    snapshots = await GetMarketLastNHours(repo).execute(hours=hours, agent_sic_code=agent)
    return [_snapshot_to_response(s) for s in snapshots]


@router.get("/summary", response_model=MarketSummaryResponse, summary="Resumen estadístico del mercado")
async def get_market_summary(
    repo: MarketRepoDep,
    hours: Annotated[int, Query(ge=1, le=720, description="Ventana de tiempo en horas")] = 24,
    agent: Annotated[str | None, Query()] = None,
) -> MarketSummaryResponse:
    snapshots = await GetMarketLastNHours(repo).execute(hours=hours, agent_sic_code=agent)
    if not snapshots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay datos para el período solicitado",
        )

    prices = [s.spot_price_cop for s in snapshots]
    demands = [s.demand_mwh for s in snapshots]
    hydro = [s.hydrology_pct for s in snapshots]
    reservoir = [s.reservoir_level_pct for s in snapshots]
    latest = snapshots[-1]

    return MarketSummaryResponse(
        period_hours=hours,
        avg_price_cop=sum(prices) / len(prices),
        min_price_cop=min(prices),
        max_price_cop=max(prices),
        avg_demand_mwh=sum(demands) / len(demands),
        avg_hydrology_pct=sum(hydro) / len(hydro),
        avg_reservoir_pct=sum(reservoir) / len(reservoir),
        current_hydrology_status=latest.hydrology_status,
        latest_timestamp=latest.timestamp,
    )
