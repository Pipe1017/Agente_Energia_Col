"""
Router de chat libre con el LLM, contextualizado con datos del mercado actual.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import (
    AgentRepoDep, MarketRepoDep, LLMServiceDep,
)
from ....infrastructure.external.langchain_llm_adapter import LangChainLLMAdapter
from ....application.use_cases.get_market_snapshot import GetMarketSnapshot

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    agent_sic_code: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str
    model_used: str


def _build_system_prompt(agent_data: dict, market_data: dict) -> str:
    lines = [
        "Eres el Agente Energía Colombia, un analista especializado en el mercado eléctrico colombiano (SIN).",
        "Ayudas a agentes generadores a entender el mercado, tomar decisiones de oferta y analizar datos.",
        "Responde siempre en español, de forma concisa, técnica y con datos concretos cuando sea relevante.",
        "Si te preguntan algo fuera del dominio energético colombiano, redirige amablemente hacia temas del sector.",
        "",
        "=== CONTEXTO DEL MERCADO ACTUAL ===",
    ]

    if market_data:
        ts = market_data.get("timestamp", "desconocido")[:10]
        lines += [
            f"- Fecha datos: {ts}",
            f"- Precio spot: {market_data.get('spot_price_cop', 0):.0f} COP/kWh",
            f"- Estado hidrológico: {market_data.get('hydrology_status', '?')} ({market_data.get('hydrology_pct', 0):.1f}% del histórico)",
            f"- Nivel embalses: {market_data.get('reservoir_level_pct', 0):.1f}%",
        ]
        if market_data.get("precio_escasez_cop"):
            lines.append(f"- Precio de escasez: {market_data['precio_escasez_cop']:.0f} COP/kWh")
        if market_data.get("gen_hidraulica_gwh"):
            lines.append(f"- Generación hidráulica: {market_data['gen_hidraulica_gwh']:.1f} GWh/día")
        if market_data.get("gen_termica_gwh"):
            lines.append(f"- Generación térmica: {market_data['gen_termica_gwh']:.1f} GWh/día")
        if market_data.get("gen_solar_gwh"):
            lines.append(f"- Generación solar: {market_data['gen_solar_gwh']:.1f} GWh/día")

    lines += ["", "=== AGENTE CONSULTANTE ==="]

    if agent_data:
        lines += [
            f"- Nombre: {agent_data.get('name', '?')}",
            f"- Código SIC: {agent_data.get('sic_code', '?')}",
            f"- Perfil de riesgo: {agent_data.get('risk_profile', '?')}",
        ]
        if agent_data.get("installed_capacity_mw"):
            lines.append(f"- Capacidad instalada: {agent_data['installed_capacity_mw']} MW")
        if agent_data.get("variable_cost_cop_kwh"):
            lines.append(f"- Costo variable: {agent_data['variable_cost_cop_kwh']:.0f} COP/kWh")
        if agent_data.get("resources"):
            lines.append(f"- Recursos: {', '.join(agent_data['resources'])}")

    lines += [
        "",
        "=== CONTEXTO DEL MERCADO COLOMBIANO ===",
        "- Precio spot típico: 100-600 COP/kWh (bajo en hidrología buena, sube en sequía)",
        "- Precio escasez: ~580-625 COP/kWh (techo de precio fijado por CREG mensualmente)",
        "- Hidrología crítica: aportes < 60% del histórico",
        "- Horas pico: 18:00-21:00 COT",
        "- Colombia: ~70% generación hidráulica (dominante)",
        "- Semestre húmedo: abril-noviembre; seco: diciembre-marzo",
    ]

    return "\n".join(lines)


@router.post("/message", response_model=ChatResponse, summary="Chat con el agente LLM")
async def chat_message(
    body: ChatRequest,
    market_repo: MarketRepoDep,
    agent_repo: AgentRepoDep,
    llm: LLMServiceDep,
) -> ChatResponse:
    """
    Endpoint de chat libre con el LLM contextualizado.
    El sistema prompt incluye datos de mercado actuales y perfil del agente.
    """
    # Obtener contexto del mercado
    market_result = await GetMarketSnapshot(market_repo).execute(agent_sic_code=None)
    market_data: dict = {}
    if market_result and market_result.snapshot:
        s = market_result.snapshot
        market_data = {
            "timestamp": s.timestamp.isoformat(),
            "spot_price_cop": s.spot_price_cop,
            "hydrology_pct": s.hydrology_pct,
            "hydrology_status": s.hydrology_status,
            "reservoir_level_pct": s.reservoir_level_pct,
            "precio_escasez_cop": s.precio_escasez_cop,
            "gen_hidraulica_gwh": s.gen_hidraulica_gwh,
            "gen_termica_gwh": s.gen_termica_gwh,
            "gen_solar_gwh": s.gen_solar_gwh,
        }

    # Obtener datos del agente
    from ....application.use_cases.get_agents import GetAgent
    agent = await GetAgent(agent_repo).execute(body.agent_sic_code.upper())
    agent_data: dict = {}
    if agent:
        agent_data = {
            "name": agent.name,
            "sic_code": str(agent.sic_code),
            "risk_profile": agent.risk_profile.value,
            "installed_capacity_mw": agent.installed_capacity_mw,
            "variable_cost_cop_kwh": agent.variable_cost_cop_kwh,
            "resources": agent.resources,
        }

    system_prompt = _build_system_prompt(agent_data, market_data)

    # Convertir historial al formato del adapter
    history = [{"role": m.role, "content": m.content} for m in body.history]

    # El adapter expone chat() directamente (no en la interfaz ILLMService)
    adapter = llm
    if not isinstance(adapter, LangChainLLMAdapter):
        # Fallback si se inyecta un mock
        return ChatResponse(response="Chat no disponible en este entorno.", model_used="mock")

    response_text = await adapter.chat(system_prompt, body.message, history)

    model_used = (
        f"{adapter._settings.LLM_PROVIDER}:{adapter._settings.DEEPSEEK_MODEL}"
        if adapter._settings.LLM_PROVIDER != "ollama"
        else f"ollama:{adapter._settings.OLLAMA_MODEL}"
    )

    return ChatResponse(response=response_text, model_used=model_used)
