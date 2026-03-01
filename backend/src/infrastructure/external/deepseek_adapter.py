"""
DeepseekAdapter — implementa ILLMService usando OpenAI SDK con base_url de Deepseek.

Genera recomendaciones de precio de oferta para agentes del mercado eléctrico colombiano.
La respuesta del LLM se parsea a la entidad de dominio Recommendation.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI

from ...domain.entities.agent import Agent, RiskProfile
from ...domain.entities.market_data import MarketSnapshot
from ...domain.entities.prediction import PricePrediction
from ...domain.entities.recommendation import HourlyOffer, Recommendation, RiskLevel
from ...domain.services.i_llm_service import ILLMService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un experto senior en el mercado eléctrico colombiano (XM/CREG).
Tu rol es asesorar a agentes generadores sobre la estrategia óptima de oferta de precio
en la bolsa de energía (mercado spot), considerando condiciones hidrológicas,
demanda, precio actual y predicciones del modelo ML.

Conocimiento del mercado colombiano:
- Precio de escasez (2025): ~1.000 COP/kWh
- Precio típico bolsa: 200-600 COP/kWh
- Horas pico: 18:00-21:00 COT
- Recurso hidroeléctrico: 70% de la generación nacional
- Umbrales críticos: hidrología < 60% del histórico = presión alcista

Responde SIEMPRE en JSON con exactamente esta estructura:
{
  "narrative": "<análisis completo en 3-4 oraciones en español>",
  "risk_level": "low|medium|high",
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "hourly_offers": [
    {"hour": 0, "suggested_price_cop": <número>, "reasoning": "<razón breve>"},
    ...
    {"hour": 23, "suggested_price_cop": <número>, "reasoning": "<razón breve>"}
  ]
}
Incluye exactamente 24 entradas en hourly_offers (hours 0-23)."""


def _build_user_prompt(
    agent: Agent,
    prediction: PricePrediction,
    market_context: list[MarketSnapshot],
) -> str:
    """Construye el prompt de usuario con contexto de mercado y predicciones."""
    recent = market_context[-1] if market_context else None
    prices_72h = [s.spot_price_cop for s in market_context[-72:]]
    avg_72h = sum(prices_72h) / len(prices_72h) if prices_72h else 0
    hydro = recent.hydrology_pct if recent else 85.0

    if hydro < 60:
        hydro_label = f"CRÍTICA ({hydro:.0f}%) — riesgo de escasez"
    elif hydro < 80:
        hydro_label = f"BAJA ({hydro:.0f}%) — presión al alza"
    else:
        hydro_label = f"NORMAL ({hydro:.0f}%)"

    # Contexto del agente
    agent_ctx = [
        f"- Nombre: {agent.name} (SIC: {agent.sic_code})",
        f"- Perfil de riesgo: {agent.risk_profile.value}",
    ]
    if agent.installed_capacity_mw:
        agent_ctx.append(f"- Capacidad instalada: {agent.installed_capacity_mw:.0f} MW")
    if agent.variable_cost_cop_kwh:
        agent_ctx.append(f"- Costo variable declarado: {agent.variable_cost_cop_kwh:.2f} COP/kWh")

    # Predicciones hora a hora
    pred_lines = []
    for hp in prediction.hourly_predictions:
        pred_lines.append(
            f"  H{hp.target_hour.hour:02d}: {hp.predicted_cop:.1f} COP/kWh "
            f"[{hp.lower_bound_cop:.1f} – {hp.upper_bound_cop:.1f}]"
        )

    return f"""AGENTE:
{chr(10).join(agent_ctx)}

CONDICIONES DE MERCADO (última hora):
- Precio spot actual: {recent.spot_price_cop:.2f} COP/kWh
- Demanda SIN: {recent.demand_mwh:.0f} MWh
- Condición hidrológica: {hydro_label}
- Nivel embalses: {recent.reservoir_level_pct:.1f}%
- Despacho térmico: {recent.thermal_dispatch_pct:.1f}%
- Precio promedio 72h: {avg_72h:.2f} COP/kWh

PREDICCIONES MODELO ML (próximas 24h):
{chr(10).join(pred_lines)}

Genera la estrategia de oferta óptima para las próximas 24 horas
considerando el perfil de riesgo del agente ({agent.risk_profile.value}).
Un perfil conservador prioriza despacho seguro sobre margen; agresivo maximiza ingreso."""


class DeepseekAdapter(ILLMService):

    def __init__(self, api_key: str, model: str = "deepseek-chat") -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        self._model = model

    async def generate_recommendation(
        self,
        agent: Agent,
        prediction: PricePrediction,
        market_context: list[MarketSnapshot],
    ) -> Recommendation:
        if not market_context:
            raise ValueError("market_context no puede estar vacío")

        user_prompt = _build_user_prompt(agent, prediction, market_context)

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.error("Error llamando Deepseek API: %s", exc)
            raise RuntimeError(f"LLM no disponible: {exc}") from exc

        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Deepseek no retornó JSON válido: %s", raw[:200])
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

        # Mapear risk_level del LLM al enum de dominio
        risk_map = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM, "high": RiskLevel.HIGH}
        risk_level = risk_map.get(data.get("risk_level", "medium"), RiskLevel.MEDIUM)

        return Recommendation(
            id=uuid.uuid4(),
            agent_sic_code=str(agent.sic_code),
            generated_at=datetime.now(timezone.utc),
            prediction_id=prediction.id,
            narrative=data.get("narrative", ""),
            hourly_offers=hourly_offers,
            risk_level=risk_level,
            key_factors=data.get("key_factors", []),
            llm_model_used=self._model,
        )

    async def health_check(self) -> bool:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception:
            return False
