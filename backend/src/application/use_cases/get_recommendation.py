"""
Use Cases: Recommendation

- GetLatestRecommendation  → última recomendación para un agente
- ListRecommendations      → histórico paginado
- GenerateRecommendation   → genera una nueva recomendación on-demand
  (llama al LLM — usado desde el endpoint /recommendations/generate)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...domain.entities.recommendation import Recommendation
from ...domain.repositories.i_recommendation_repository import IRecommendationRepository
from ...domain.repositories.i_market_repository import IMarketRepository
from ...domain.repositories.i_prediction_repository import IPredictionRepository
from ...domain.repositories.i_agent_repository import IAgentRepository
from ...domain.services.i_llm_service import ILLMService
from ...domain.value_objects.sic_code import SICCode


class GetLatestRecommendation:

    def __init__(self, recommendation_repo: IRecommendationRepository) -> None:
        self._repo = recommendation_repo

    async def execute(self, sic_code: str) -> Recommendation | None:
        return await self._repo.get_latest(sic_code)


class ListRecommendations:

    def __init__(self, recommendation_repo: IRecommendationRepository) -> None:
        self._repo = recommendation_repo

    async def execute(
        self,
        sic_code: str,
        start: datetime,
        end: datetime,
    ) -> list[Recommendation]:
        return await self._repo.get_range(sic_code, start=start, end=end)


@dataclass
class GenerateRecommendationCommand:
    sic_code: str
    context_hours: int = 72     # horas de contexto histórico para el LLM


class GenerateRecommendation:
    """
    Genera una recomendación on-demand para el agente usando el modelo champion.
    Persiste la recomendación en BD y la retorna.
    """

    def __init__(
        self,
        agent_repo: IAgentRepository,
        market_repo: IMarketRepository,
        prediction_repo: IPredictionRepository,
        recommendation_repo: IRecommendationRepository,
        llm_service: ILLMService,
    ) -> None:
        self._agents = agent_repo
        self._market = market_repo
        self._predictions = prediction_repo
        self._recommendations = recommendation_repo
        self._llm = llm_service

    async def execute(self, cmd: GenerateRecommendationCommand) -> Recommendation:
        sic = SICCode(cmd.sic_code)

        agent = await self._agents.get_by_sic(sic)
        if agent is None:
            raise ValueError(f"Agente {cmd.sic_code} no configurado")

        # Obtener última predicción disponible
        prediction = await self._predictions.get_latest(sic)
        if prediction is None:
            raise ValueError(
                f"Sin predicción disponible para {cmd.sic_code}. "
                "Espere a que el modelo champion genere una."
            )

        # Contexto histórico de mercado para el LLM
        market_context = await self._market.get_last_n_hours(cmd.context_hours)
        if not market_context:
            raise ValueError("Sin datos de mercado disponibles")

        recommendation = await self._llm.generate_recommendation(
            agent=agent,
            prediction=prediction,
            market_context=market_context,
        )

        saved = await self._recommendations.save(recommendation)
        return saved
