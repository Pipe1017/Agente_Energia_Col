"""
Identificadores de métricas de la API pública de XM.

Dos sistemas conviven:
  1. SINERGOX (servapibi.xm.com.co) — datos en tiempo casi real, POST con MetricId
  2. SIMEM    (simem.co)             — histórico largo plazo, GET con datasetId

Uso en pydataxm:
    from pydataxm.pydataxm import ReadDB
    api = ReadDB()
    df = api.request_data(
        metric=SinergoxMetrics.SPOT_PRICE,
        entity="Sistema",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

Fuente: https://github.com/EquipoAnaliticaXM/API_XM
        https://www.simem.co/
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ------------------------------------------------------------------
# SINERGOX — métricas en tiempo casi real (por hora / día / mes)
# ------------------------------------------------------------------
class SinergoxMetrics:
    """MetricId strings para la API SINERGOX (servapibi.xm.com.co)."""

    # Precio y transacciones
    SPOT_PRICE = "PrecioMercado"              # COP/kWh — precio bolsa nacional
    SCARCITY_PRICE = "PrecioEscasez"          # precio de escasez regulatorio
    CONTRACT_PRICE = "PrecioContrato"         # precio promedio contratos

    # Demanda
    COMMERCIAL_DEMAND = "DemandaComercial"    # demanda comercial total SIN
    DEMAND_SIN = "DemandaDespacho"            # demanda despachada SIN

    # Generación
    REAL_GENERATION = "GeneracionReal"        # generación real por recurso/agente
    IDEAL_GENERATION = "GeneracionIdeal"      # generación ideal (sin restricciones)
    NET_EFFECTIVE_CAPACITY = "CapacidadEfectivaNeta"  # capacidad disponible

    # Hidrología (crítico en Colombia — ~70% hidro)
    HYDRO_CONTRIBUTIONS = "AportesHidro"      # aportes hidrológicos m³/s
    RESERVOIR_LEVEL = "NivelEmbalse"          # nivel de embalse por planta
    RESERVOIR_VOLUME = "VolumenEmbalse"       # volumen útil en GWh

    # Despacho y restricciones
    THERMAL_DISPATCH = "GeneracionTermica"    # generación térmica total
    DECLARED_CAPACITY = "CapacidadDeclarada"  # capacidad declarada por agente
    FIRM_ENERGY = "ObligacionEnergia"         # OEF por agente

    # Exportaciones / importaciones
    INTERNATIONAL_EXCHANGE = "IntercambioInternacional"


# ------------------------------------------------------------------
# SIMEM — datasets de histórico largo plazo (ID alfanumérico 6 chars)
# Fuente: Catálogo SIMEM  →  CatalogSIMEM('Datasets').get_data()
# ⚠️  Validar IDs contra el catálogo oficial antes de usar en producción
# ------------------------------------------------------------------
class SimemDatasets:
    """Dataset IDs para la API SIMEM (simem.co/backend-files/api/PublicData)."""

    # Precio bolsa
    SPOT_PRICE_HOURLY = "B7F2C4"          # precio bolsa horario
    SPOT_PRICE_DAILY = "A3E8B1"           # precio bolsa diario promedio

    # Demanda
    DEMAND_BASIC = "c1b851"               # demanda real (nivel básico)
    DEMAND_BY_AGENT = "b7917"             # demanda desagregada por agente

    # Hidrología
    HYDRO_CONTRIBUTIONS = "F1A2D3"        # aportes hidrológicos diarios
    RESERVOIR_DAILY = "E9C5B2"            # embalses diarios por planta

    # Generación
    GENERATION_HOURLY = "D4F8A1"          # generación horaria por recurso
    GENERATION_BY_AGENT = "C2B9E4"        # generación diaria por agente

    # Regulatorio
    FIRM_ENERGY_OEF = "B5D1F7"            # obligaciones de energía firme
    SCARCITY_EVENTS = "A8C3E6"            # eventos de escasez declarados


# ------------------------------------------------------------------
# Entidades de consulta en SINERGOX
# ------------------------------------------------------------------
class SinergoxEntity:
    SYSTEM = "Sistema"      # agregado del SIN completo
    AGENT = "Agente"        # por agente generador (filtrar con sic_code)
    RESOURCE = "Recurso"    # por planta/recurso individual
    RESERVOIR = "Embalse"   # por embalse específico
    RIVER = "Rio"           # por cuenca hidrográfica


# ------------------------------------------------------------------
# Grupos temáticos para los DAGs de ingestion
# Cada grupo define qué métricas descarga el DAG xm_ingestion_dag
# ------------------------------------------------------------------
@dataclass(frozen=True)
class MetricGroup:
    name: str
    metrics: list[str]        # SinergoxMetrics values
    entity: str               # SinergoxEntity value
    frequency: str            # "hourly" | "daily"
    priority: int             # 1 = más importante (se descarga primero)


INGESTION_GROUPS: list[MetricGroup] = [
    MetricGroup(
        name="prices",
        metrics=[SinergoxMetrics.SPOT_PRICE, SinergoxMetrics.SCARCITY_PRICE],
        entity=SinergoxEntity.SYSTEM,
        frequency="hourly",
        priority=1,
    ),
    MetricGroup(
        name="demand",
        metrics=[SinergoxMetrics.COMMERCIAL_DEMAND],
        entity=SinergoxEntity.SYSTEM,
        frequency="hourly",
        priority=2,
    ),
    MetricGroup(
        name="hydrology",
        metrics=[SinergoxMetrics.HYDRO_CONTRIBUTIONS, SinergoxMetrics.RESERVOIR_LEVEL],
        entity=SinergoxEntity.SYSTEM,
        frequency="daily",
        priority=3,
    ),
    MetricGroup(
        name="generation",
        metrics=[SinergoxMetrics.REAL_GENERATION, SinergoxMetrics.IDEAL_GENERATION],
        entity=SinergoxEntity.SYSTEM,
        frequency="hourly",
        priority=4,
    ),
]
