from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.agent import Agent
from ..entities.market_data import MarketSnapshot
from ..entities.prediction import PricePrediction
from ..entities.recommendation import Recommendation


class ILLMService(ABC):
    """
    Servicio de generación de recomendaciones estratégicas via LLM.
    Implementación actual: DeepseekAdapter.
    Sustituible por cualquier otro LLM sin tocar el dominio.
    """

    @abstractmethod
    async def generate_recommendation(
        self,
        agent: Agent,
        prediction: PricePrediction,
        market_context: list[MarketSnapshot],  # últimas 72h del mercado
    ) -> Recommendation:
        """
        Genera una recomendación de oferta para las próximas 24h.

        El LLM recibe:
        - Perfil del agente (nombre, SIC, riesgo, capacidad si disponible)
        - Predicción de precio hora a hora
        - Contexto histórico de mercado (precio, demanda, hidrología)

        Retorna una Recommendation con narrative + hourly_offers + risk_level.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica conectividad con la API del LLM."""
        ...
