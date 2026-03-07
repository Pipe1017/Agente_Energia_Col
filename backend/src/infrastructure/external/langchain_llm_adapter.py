"""
LangChainLLMAdapter — implementa ILLMService usando LangChain.

Proveedor seleccionado por la variable de entorno LLM_PROVIDER:
  "deepseek" (default) → ChatOpenAI con base_url de Deepseek (producción)
  "ollama"             → ChatOllama sin API key (desarrollo local)
  "openai"             → ChatOpenAI estándar

La lógica de dominio (prompt, parseo, entidad Recommendation) se reutiliza
del módulo deepseek_adapter sin modificación. Solo cambia la capa de transporte.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ...config import Settings
from ...domain.entities.agent import Agent
from ...domain.entities.market_data import MarketSnapshot
from ...domain.entities.prediction import PricePrediction
from ...domain.entities.recommendation import HourlyOffer, Recommendation, RiskLevel
from ...domain.services.i_llm_service import ILLMService
from .deepseek_adapter import SYSTEM_PROMPT, _build_user_prompt

logger = logging.getLogger(__name__)


def _build_chat_model(settings: Settings, json_mode: bool = True) -> BaseChatModel:
    """
    Factory que instancia el ChatModel correcto según LLM_PROVIDER.
    Soporta hot-swap entre Deepseek (prod) y Ollama (dev) sin tocar el dominio.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama  # type: ignore[import-untyped]

        logger.info("LLM provider: Ollama (%s) @ %s", settings.OLLAMA_MODEL, settings.OLLAMA_BASE_URL)
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            format="json",
            temperature=settings.DEEPSEEK_TEMPERATURE,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]

        logger.info("LLM provider: OpenAI (%s)", settings.DEEPSEEK_MODEL)
        kwargs = {"model_kwargs": {"response_format": {"type": "json_object"}}} if json_mode else {}
        return ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL,
            temperature=settings.DEEPSEEK_TEMPERATURE,
            max_tokens=settings.DEEPSEEK_MAX_TOKENS,
            **kwargs,
        )

    # Default: Deepseek (protocolo OpenAI-compatible)
    from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]

    logger.info("LLM provider: Deepseek (%s) json_mode=%s", settings.DEEPSEEK_MODEL, json_mode)
    kwargs = {"model_kwargs": {"response_format": {"type": "json_object"}}} if json_mode else {}
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=settings.DEEPSEEK_TEMPERATURE,
        max_tokens=settings.DEEPSEEK_MAX_TOKENS,
        **kwargs,
    )


class LangChainLLMAdapter(ILLMService):
    """
    Implementación de ILLMService usando LangChain como capa de abstracción.
    El proveedor (Deepseek, Ollama, OpenAI) se elige mediante la variable
    de entorno LLM_PROVIDER sin cambios en la lógica de negocio.
    """

    def __init__(self, settings: Settings) -> None:
        self._llm = _build_chat_model(settings, json_mode=True)   # para recommendations (JSON)
        self._chat_llm = _build_chat_model(settings, json_mode=False)  # para chat libre (texto)
        self._settings = settings

    async def generate_recommendation(
        self,
        agent: Agent,
        prediction: PricePrediction,
        market_context: list[MarketSnapshot],
    ) -> Recommendation:
        if not market_context:
            raise ValueError("market_context no puede estar vacío")

        user_prompt = _build_user_prompt(agent, prediction, market_context)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = await self._llm.ainvoke(messages)
        except Exception as exc:
            logger.error("Error llamando LLM (%s): %s", self._settings.LLM_PROVIDER, exc)
            raise RuntimeError(f"LLM no disponible: {exc}") from exc

        raw = response.content if hasattr(response, "content") else str(response)

        try:
            data = json.loads(raw)  # type: ignore[arg-type]
        except json.JSONDecodeError as exc:
            preview = str(raw)[:200]
            logger.error("LLM no retornó JSON válido: %s", preview)
            raise ValueError("Respuesta LLM inválida") from exc

        # Construir HourlyOffer para cada hora
        now_date = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        hourly_offers: list[HourlyOffer] = []
        for entry in data.get("hourly_offers", []):
            hour_ts = now_date.replace(hour=int(entry["hour"]))
            hourly_offers.append(
                HourlyOffer(
                    hour=hour_ts,
                    suggested_price_cop=float(entry["suggested_price_cop"]),
                    reasoning=entry.get("reasoning", ""),
                )
            )

        if not hourly_offers:
            raise ValueError("LLM no generó hourly_offers")

        risk_map = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM, "high": RiskLevel.HIGH}
        risk_level = risk_map.get(data.get("risk_level", "medium"), RiskLevel.MEDIUM)

        model_name = (
            f"{self._settings.LLM_PROVIDER}:{self._settings.DEEPSEEK_MODEL}"
            if self._settings.LLM_PROVIDER != "ollama"
            else f"ollama:{self._settings.OLLAMA_MODEL}"
        )

        return Recommendation(
            id=uuid.uuid4(),
            agent_sic_code=str(agent.sic_code),
            generated_at=datetime.now(timezone.utc),
            prediction_id=prediction.id,
            narrative=data.get("narrative", ""),
            hourly_offers=hourly_offers,
            risk_level=risk_level,
            key_factors=data.get("key_factors", []),
            llm_model_used=model_name,
        )

    async def chat(self, system_prompt: str, user_message: str, history: list[dict] | None = None) -> str:
        """Chat libre con el LLM, con system prompt personalizable y historial opcional."""
        from langchain_core.messages import AIMessage

        messages = [SystemMessage(content=system_prompt)]
        for turn in (history or []):
            if turn.get("role") == "user":
                messages.append(HumanMessage(content=turn["content"]))
            elif turn.get("role") == "assistant":
                messages.append(AIMessage(content=turn["content"]))
        messages.append(HumanMessage(content=user_message))

        try:
            response = await self._chat_llm.ainvoke(messages)
        except Exception as exc:
            logger.error("Error en chat LLM (%s): %s", self._settings.LLM_PROVIDER, exc)
            raise RuntimeError(f"LLM no disponible: {exc}") from exc

        content = response.content if hasattr(response, "content") else str(response)
        # Si el LLM devuelve JSON (modo json_object forzado), intentar extraer texto
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                content = parsed.get("response") or parsed.get("answer") or parsed.get("text") or content
        except (json.JSONDecodeError, TypeError):
            pass
        return str(content)

    async def health_check(self) -> bool:
        try:
            response = await self._llm.ainvoke([HumanMessage(content="ping")])
            return bool(response.content)
        except Exception:
            return False
