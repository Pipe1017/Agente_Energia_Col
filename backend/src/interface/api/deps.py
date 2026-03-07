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
from ...infrastructure.db.repositories.pg_prediction_repository import PgPredictionRepository
from ...infrastructure.db.repositories.pg_recommendation_repository import PgRecommendationRepository
from ...infrastructure.mlflow.mlflow_model_repository import MlflowModelRepository
from ...domain.services.i_llm_service import ILLMService
from ...infrastructure.external.langchain_llm_adapter import LangChainLLMAdapter

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


@lru_cache(maxsize=1)
def _get_mlflow_model_repo() -> MlflowModelRepository:
    settings = get_settings()
    return MlflowModelRepository(
        tracking_uri=settings.MLFLOW_TRACKING_URI,
        registered_model_name="xgboost_price_predictor",
    )


def get_model_repo() -> MlflowModelRepository:
    return _get_mlflow_model_repo()


def get_prediction_repo(session: SessionDep) -> PgPredictionRepository:
    return PgPredictionRepository(session)


def get_recommendation_repo(session: SessionDep) -> PgRecommendationRepository:
    return PgRecommendationRepository(session)


# ------------------------------------------------------------------
# Servicios externos
# ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_llm_adapter() -> LangChainLLMAdapter:
    """
    Singleton — se instancia una sola vez.
    El proveedor (Deepseek | Ollama | OpenAI) se determina por LLM_PROVIDER.
    """
    return LangChainLLMAdapter(get_settings())


def get_llm_service() -> ILLMService:
    return _get_llm_adapter()


# ------------------------------------------------------------------
# Alias tipados para routers
# ------------------------------------------------------------------

AgentRepoDep = Annotated[PgAgentRepository, Depends(get_agent_repo)]
MarketRepoDep = Annotated[PgMarketRepository, Depends(get_market_repo)]
ModelRepoDep = Annotated[MlflowModelRepository, Depends(get_model_repo)]
PredictionRepoDep = Annotated[PgPredictionRepository, Depends(get_prediction_repo)]
RecommendationRepoDep = Annotated[PgRecommendationRepository, Depends(get_recommendation_repo)]
LLMServiceDep = Annotated[ILLMService, Depends(get_llm_service)]
