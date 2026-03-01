"""
Inyección de dependencias FastAPI.

Patrón: cada router importa las dependencias que necesita usando Depends().
Las factories son funciones puras que reciben la sesión async y retornan
el repositorio o use case concreto.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings, Settings
from ...infrastructure.db.session import get_session
from ...infrastructure.db.repositories.pg_agent_repository import PgAgentRepository
from ...infrastructure.db.repositories.pg_market_repository import PgMarketRepository
from ...infrastructure.db.repositories.pg_model_repository import PgModelRepository
from ...infrastructure.db.repositories.pg_prediction_repository import PgPredictionRepository
from ...infrastructure.db.repositories.pg_recommendation_repository import PgRecommendationRepository
from ...infrastructure.external.deepseek_adapter import DeepseekAdapter

# ------------------------------------------------------------------
# Alias tipados para inyección limpia en routers
# ------------------------------------------------------------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ------------------------------------------------------------------
# Repositorios
# ------------------------------------------------------------------

def get_agent_repo(session: SessionDep) -> PgAgentRepository:
    return PgAgentRepository(session)


def get_market_repo(session: SessionDep) -> PgMarketRepository:
    return PgMarketRepository(session)


def get_model_repo(session: SessionDep) -> PgModelRepository:
    return PgModelRepository(session)


def get_prediction_repo(session: SessionDep) -> PgPredictionRepository:
    return PgPredictionRepository(session)


def get_recommendation_repo(session: SessionDep) -> PgRecommendationRepository:
    return PgRecommendationRepository(session)


# ------------------------------------------------------------------
# Servicios externos
# ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_deepseek_adapter() -> DeepseekAdapter:
    """Singleton — el cliente HTTP se reutiliza entre requests."""
    settings = get_settings()
    return DeepseekAdapter(
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.DEEPSEEK_MODEL,
    )


def get_llm_service() -> DeepseekAdapter:
    return _get_deepseek_adapter()


# ------------------------------------------------------------------
# Alias tipados para routers
# ------------------------------------------------------------------

AgentRepoDep = Annotated[PgAgentRepository, Depends(get_agent_repo)]
MarketRepoDep = Annotated[PgMarketRepository, Depends(get_market_repo)]
ModelRepoDep = Annotated[PgModelRepository, Depends(get_model_repo)]
PredictionRepoDep = Annotated[PgPredictionRepository, Depends(get_prediction_repo)]
RecommendationRepoDep = Annotated[PgRecommendationRepository, Depends(get_recommendation_repo)]
LLMServiceDep = Annotated[DeepseekAdapter, Depends(get_llm_service)]
