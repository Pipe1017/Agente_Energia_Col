from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class RiskLevel(str, Enum):
    LOW = "low"       # estrategia conservadora, despacho casi seguro
    MEDIUM = "medium" # balance ingreso / probabilidad de despacho
    HIGH = "high"     # estrategia agresiva, máximo ingreso potencial


@dataclass(frozen=True)
class HourlyOffer:
    """Precio de oferta sugerido para una hora específica."""

    hour: datetime
    suggested_price_cop: float   # COP/kWh
    reasoning: str               # explicación breve del LLM para esa hora

    def __post_init__(self) -> None:
        if self.suggested_price_cop < 0:
            raise ValueError(f"suggested_price_cop no puede ser negativo: {self.suggested_price_cop}")
        if not self.reasoning:
            raise ValueError("reasoning no puede estar vacío")

    @property
    def is_peak_hour(self) -> bool:
        return 18 <= self.hour.hour <= 21


@dataclass
class Recommendation:
    """
    Recomendación estratégica de oferta generada por el agente LLM (Deepseek).
    Vinculada a una predicción de precio y contextualizada para un agente específico.
    """

    id: UUID
    agent_sic_code: str
    generated_at: datetime
    prediction_id: UUID

    # Salida del LLM
    narrative: str               # análisis narrativo completo
    hourly_offers: list[HourlyOffer]
    risk_level: RiskLevel
    key_factors: list[str]       # ["hidrología baja", "demanda pico 18-21h", ...]
    llm_model_used: str          # "deepseek-chat"

    def __post_init__(self) -> None:
        if not self.narrative:
            raise ValueError("narrative no puede estar vacío")
        if not self.hourly_offers:
            raise ValueError("hourly_offers no puede estar vacío")
        if not self.key_factors:
            raise ValueError("key_factors no puede estar vacío")

    @property
    def avg_suggested_price(self) -> float:
        if not self.hourly_offers:
            return 0.0
        return sum(o.suggested_price_cop for o in self.hourly_offers) / len(self.hourly_offers)

    @property
    def peak_offers(self) -> list[HourlyOffer]:
        return [o for o in self.hourly_offers if o.is_peak_hour]

    @property
    def summary(self) -> str:
        """Resumen de una línea para la vista ejecutiva."""
        avg = self.avg_suggested_price
        return (
            f"Oferta sugerida promedio: COP ${avg:,.0f}/kWh | "
            f"Riesgo: {self.risk_level.value} | "
            f"Factores clave: {', '.join(self.key_factors[:2])}"
        )
