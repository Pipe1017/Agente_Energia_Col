from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class MarketSnapshot:
    """
    Instantánea del mercado eléctrico colombiano en un momento dado.
    Fuente: API pública de XM (SIMEM + SINERGOX).

    Todos los campos son del SIN (Sistema Interconectado Nacional)
    salvo que agent_sic_code esté presente, en cuyo caso son del agente.
    """

    id: UUID
    timestamp: datetime

    # Precio y transacciones
    spot_price_cop: float           # COP/kWh — precio de bolsa nacional

    # Demanda
    demand_mwh: float               # MWh — demanda total SIN

    # Hidrología (factor dominante en Colombia — ~70% hidro)
    hydrology_pct: float            # % vs promedio histórico (100 = normal)
    reservoir_level_pct: float      # % nivel de embalses sistema

    # Despacho
    thermal_dispatch_pct: float     # % de generación que es térmica

    # Contexto de agente (None = datos del sistema completo)
    agent_sic_code: str | None = None

    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not (0.0 <= self.hydrology_pct <= 300.0):
            raise ValueError(f"hydrology_pct fuera de rango: {self.hydrology_pct}")
        if not (0.0 <= self.reservoir_level_pct <= 100.0):
            raise ValueError(f"reservoir_level_pct fuera de rango: {self.reservoir_level_pct}")
        if not (0.0 <= self.thermal_dispatch_pct <= 100.0):
            raise ValueError(f"thermal_dispatch_pct fuera de rango: {self.thermal_dispatch_pct}")

    @property
    def is_hydrology_critical(self) -> bool:
        """Hidrología por debajo del 60% del histórico → alerta."""
        return self.hydrology_pct < 60.0

    @property
    def is_reservoir_low(self) -> bool:
        """Embalses por debajo del 30% → nivel de alerta."""
        return self.reservoir_level_pct < 30.0

    @property
    def hydrology_status(self) -> str:
        if self.hydrology_pct >= 110:
            return "alta"
        if self.hydrology_pct >= 80:
            return "normal"
        if self.hydrology_pct >= 60:
            return "baja"
        return "crítica"
