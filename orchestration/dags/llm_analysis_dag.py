"""
DAG: llm_analysis
Schedule: cada hora (sincronizado con xm_ingestion)

Para cada agente SIC configurado, genera una recomendación de precio
usando el modelo champion + Deepseek (OpenAI-compatible API).

Flujo por agente:
  1. load_champion_model    → carga artefactos del champion desde MinIO
  2. generate_predictions   → predicción 24h con intervalos de confianza
  3. generate_llm_analysis  → prompt estructurado → Deepseek → recomendación
  4. store_recommendations  → persiste en PostgreSQL tabla recommendations

Las recomendaciones se generan para cada agente en la lista ACTIVE_AGENTS.
Sin agentes configurados → DAG completa sin acciones (idempotente).
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "ml-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Agentes activos para generación de recomendaciones
# En producción esto vendría de la BD, aquí usamos lista estática configurable
ACTIVE_AGENTS = ["EPMC", "CLSI", "EMGS"]   # EPM, Celsia, Emgesa


@dag(
    dag_id="llm_analysis",
    schedule="30 * * * *",   # cada hora a los :30 (después de xm_ingestion)
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["llm", "recommendations", "deepseek"],
    doc_md=__doc__,
)
def llm_analysis_dag():

    @task(task_id="load_market_context")
    def load_market_context() -> dict:
        """
        Carga el snapshot de mercado más reciente para construir el contexto LLM.
        Incluye últimas 24 horas de datos y tendencias.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from sqlalchemy import text
        import pandas as pd

        engine = get_db_engine()
        query = text("""
            SELECT
                timestamp, spot_price_cop, demand_mwh,
                hydrology_pct, reservoir_level_pct, thermal_dispatch_pct
            FROM market_data
            WHERE agent_sic_code IS NULL
            ORDER BY timestamp DESC
            LIMIT 48
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn)

        if df.empty:
            logger.warning("Sin datos de mercado recientes")
            return {}

        df = df.sort_values("timestamp")
        latest = df.iloc[-1]

        # Estadísticas de las últimas 24 horas
        last_24h = df.tail(24)
        context = {
            "latest_timestamp": str(latest["timestamp"]),
            "spot_price_cop": float(latest["spot_price_cop"]),
            "demand_mwh": float(latest["demand_mwh"]),
            "hydrology_pct": float(latest["hydrology_pct"]),
            "reservoir_level_pct": float(latest["reservoir_level_pct"]),
            "thermal_dispatch_pct": float(latest["thermal_dispatch_pct"]),
            "price_24h_avg": float(last_24h["spot_price_cop"].mean()),
            "price_24h_max": float(last_24h["spot_price_cop"].max()),
            "price_24h_min": float(last_24h["spot_price_cop"].min()),
            "price_trend_pct": float(
                (latest["spot_price_cop"] - last_24h.iloc[0]["spot_price_cop"])
                / last_24h.iloc[0]["spot_price_cop"] * 100
            ) if len(last_24h) > 1 else 0.0,
            "history": last_24h[["timestamp", "spot_price_cop"]].assign(
                timestamp=lambda d: d["timestamp"].astype(str)
            ).to_dict(orient="records"),
        }

        logger.info("Contexto de mercado cargado: precio=%.2f COP | hidro=%.1f%%",
                    context["spot_price_cop"], context["hydrology_pct"])
        return context

    @task(task_id="load_champion_and_predict")
    def load_champion_and_predict(market_context: dict) -> dict:
        """
        Carga el modelo champion y genera predicciones 24h con intervalos.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")
        from dags._utils import get_db_engine, get_model_registry
        from sqlalchemy import text
        import json

        if not market_context:
            return {}

        # Obtener artifact_path del champion
        engine = get_db_engine()
        query = text("""
            SELECT artifact_path, metrics, version
            FROM model_versions
            WHERE stage = 'production' AND is_champion = true
            ORDER BY trained_at DESC
            LIMIT 1
        """)

        with engine.connect() as conn:
            row = conn.execute(query).fetchone()

        if not row:
            logger.warning("Sin champion disponible — omitiendo predicción")
            return {}

        artifact_path = row.artifact_path
        model_metrics = row.metrics if isinstance(row.metrics, dict) else json.loads(row.metrics)
        model_version = row.version

        # Cargar modelo desde MinIO
        from models.price_prediction.xgboost_model import XGBoostPriceModel
        registry = get_model_registry()
        model = registry.load_model(XGBoostPriceModel, artifact_path)

        # Construir features para las próximas 24 horas
        import pandas as pd
        import numpy as np
        from datetime import datetime, timezone, timedelta
        from features.feature_pipeline import build_feature_matrix, PRICE_PREDICTION_FEATURES

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        future_timestamps = [now + timedelta(hours=h) for h in range(1, 25)]

        # Construir DataFrame sintético para predicción futura
        # Usando últimos valores de mercado como base
        history = pd.DataFrame(market_context.get("history", []))
        history["timestamp"] = pd.to_datetime(history["timestamp"])

        # Crear filas futuras con valores de mercado proyectados
        future_rows = []
        for ts in future_timestamps:
            future_rows.append({
                "timestamp": ts,
                "spot_price_cop": market_context["spot_price_cop"],
                "demand_mwh": market_context["demand_mwh"],
                "hydrology_pct": market_context["hydrology_pct"],
                "reservoir_level_pct": market_context["reservoir_level_pct"],
                "thermal_dispatch_pct": market_context["thermal_dispatch_pct"],
            })

        future_df = pd.DataFrame(future_rows)

        # Combinar histórico + futuro para calcular lags
        combined = pd.concat([history.assign(
            demand_mwh=market_context["demand_mwh"],
            hydrology_pct=market_context["hydrology_pct"],
            reservoir_level_pct=market_context["reservoir_level_pct"],
            thermal_dispatch_pct=market_context["thermal_dispatch_pct"],
        ), future_df], ignore_index=True)

        combined["timestamp"] = pd.to_datetime(combined["timestamp"])
        feature_df = build_feature_matrix(combined, drop_na=False)

        # Solo predecir filas futuras
        future_features = feature_df[feature_df["timestamp"].isin(future_timestamps)].copy()
        future_features = future_features.dropna(subset=PRICE_PREDICTION_FEATURES[:10])

        if future_features.empty:
            logger.warning("No hay features válidas para predicción futura")
            return {}

        X = future_features[PRICE_PREDICTION_FEATURES]
        preds, lower, upper = model.predict_with_intervals(X)

        predictions = []
        for i, ts in enumerate(future_features["timestamp"]):
            predictions.append({
                "timestamp": str(ts),
                "predicted_price": float(preds[i]),
                "lower_bound": float(lower[i]),
                "upper_bound": float(upper[i]),
            })

        logger.info("Predicciones generadas: %d horas | prom=%.2f COP",
                    len(predictions),
                    np.mean([p["predicted_price"] for p in predictions]))

        return {
            "predictions": predictions,
            "model_version": model_version,
            "model_metrics": model_metrics,
        }

    @task(task_id="generate_llm_recommendation")
    def generate_llm_recommendation(
        market_context: dict,
        prediction_result: dict,
        agent_sic_code: str,
    ) -> dict:
        """
        Construye prompt estructurado y llama a Deepseek para generar
        la recomendación de precio oferta para el agente.
        """
        import sys, os, json
        sys.path.insert(0, "/opt/airflow")

        if not market_context or not prediction_result.get("predictions"):
            logger.warning("Sin contexto o predicciones para %s", agent_sic_code)
            return {}

        from openai import OpenAI

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY no configurado")

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )

        predictions = prediction_result["predictions"]
        avg_pred = sum(p["predicted_price"] for p in predictions) / len(predictions)
        peak_preds = [p for p in predictions
                      if 17 <= int(p["timestamp"][11:13]) <= 21]
        avg_peak = (sum(p["predicted_price"] for p in peak_preds) / len(peak_preds)
                    if peak_preds else avg_pred)

        # Evaluar condiciones hidrológicas
        hydro = market_context["hydrology_pct"]
        if hydro < 60:
            hydro_status = "CRÍTICA (< 60% del histórico) — alta presión alcista sobre precios"
        elif hydro < 80:
            hydro_status = "BAJA (60-80%) — presión moderada al alza"
        else:
            hydro_status = f"NORMAL ({hydro:.0f}%) — condiciones hidrológicas favorables"

        system_prompt = """Eres un experto en el mercado eléctrico colombiano (XM/CREG).
Tu rol es asesorar a agentes generadores sobre la estrategia óptima de oferta de precio
en la bolsa de energía (mercado spot), considerando condiciones hidrológicas,
demanda, precio actual y predicciones del modelo ML.

Responde SIEMPRE en JSON con exactamente esta estructura:
{
  "recommended_offer_price_cop": <número>,
  "confidence": "alta|media|baja",
  "risk_level": "low|medium|high",
  "rationale": "<explicación concisa en 2-3 oraciones>",
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "hourly_strategy": {
    "off_peak": <precio sugerido para horas valle (0-6h)>,
    "mid_peak": <precio sugerido para horas intermedias (7-17h)>,
    "peak": <precio sugerido para horas pico (18-22h)>
  },
  "alerts": ["<alerta si aplica>"]
}"""

        user_prompt = f"""Agente SIC: {agent_sic_code}

CONDICIONES ACTUALES DEL MERCADO:
- Precio spot actual: {market_context['spot_price_cop']:.2f} COP/kWh
- Demanda SIN: {market_context['demand_mwh']:.0f} MWh
- Condición hidrológica: {hydro_status}
- Nivel embalses: {market_context['reservoir_level_pct']:.1f}%
- Despacho térmico: {market_context['thermal_dispatch_pct']:.1f}%
- Tendencia precio 24h: {market_context['price_trend_pct']:+.1f}%

PREDICCIONES DEL MODELO (próximas 24 horas):
- Precio promedio predicho: {avg_pred:.2f} COP/kWh
- Precio promedio horas pico (18-21h): {avg_peak:.2f} COP/kWh
- Precio mínimo predicho: {min(p['predicted_price'] for p in predictions):.2f} COP/kWh
- Precio máximo predicho: {max(p['predicted_price'] for p in predictions):.2f} COP/kWh
- Calidad del modelo: RMSE={prediction_result['model_metrics'].get('rmse', 0):.2f} COP/kWh

¿Cuál es la estrategia de oferta de precio óptima para este agente?"""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            recommendation = json.loads(content)
            recommendation["agent_sic_code"] = agent_sic_code
            recommendation["model_version"] = prediction_result.get("model_version")
            recommendation["predictions_summary"] = {
                "avg_price": avg_pred,
                "avg_peak_price": avg_peak,
                "horizon_hours": len(predictions),
            }

            logger.info("Recomendación generada para %s: %.2f COP/kWh | riesgo=%s",
                        agent_sic_code,
                        recommendation.get("recommended_offer_price_cop", 0),
                        recommendation.get("risk_level", "?"))
            return recommendation

        except json.JSONDecodeError as e:
            logger.error("Deepseek no retornó JSON válido: %s", e)
            return {}
        except Exception as e:
            logger.error("Error llamando Deepseek para %s: %s", agent_sic_code, e)
            raise

    @task(task_id="store_recommendations")
    def store_recommendations(recommendations: list[dict]) -> dict:
        """
        Persiste las recomendaciones en PostgreSQL.
        UPSERT por (agent_sic_code, created_at truncado a hora).
        """
        import sys, uuid, json
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from datetime import datetime, timezone
        from sqlalchemy import text

        valid = [r for r in recommendations if r and r.get("recommended_offer_price_cop")]
        if not valid:
            logger.warning("Sin recomendaciones válidas para almacenar")
            return {"stored": 0}

        engine = get_db_engine()
        now = datetime.now(timezone.utc)

        with engine.begin() as conn:
            for rec in valid:
                conn.execute(text("""
                    INSERT INTO recommendations
                        (id, agent_sic_code, prediction_id, model_version_id,
                         recommended_offer_price_cop, confidence, risk_level,
                         rationale, key_factors, hourly_offers,
                         llm_model_used, created_at, valid_until)
                    VALUES
                        (:id, :sic, NULL, NULL,
                         :price, :confidence, :risk,
                         :rationale, :key_factors::jsonb, :hourly_offers::jsonb,
                         :llm_model, :created_at, :valid_until)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(uuid.uuid4()),
                    "sic": rec["agent_sic_code"],
                    "price": rec["recommended_offer_price_cop"],
                    "confidence": rec.get("confidence", "media"),
                    "risk": rec.get("risk_level", "medium"),
                    "rationale": rec.get("rationale", ""),
                    "key_factors": json.dumps(rec.get("key_factors", [])),
                    "hourly_offers": json.dumps(rec.get("hourly_strategy", {})),
                    "llm_model": "deepseek-chat",
                    "created_at": now,
                    "valid_until": now.replace(
                        hour=now.hour + 1 if now.hour < 23 else 23,
                        minute=0, second=0, microsecond=0
                    ),
                })

        logger.info("Recomendaciones almacenadas: %d", len(valid))
        return {"stored": len(valid), "agents": [r["agent_sic_code"] for r in valid]}

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    market_ctx = load_market_context()
    prediction = load_champion_and_predict(market_ctx)

    # Generar recomendaciones para cada agente activo
    recs = [
        generate_llm_recommendation(
            market_context=market_ctx,
            prediction_result=prediction,
            agent_sic_code=sic_code,
        )
        for sic_code in ACTIVE_AGENTS
    ]

    store_recommendations(recs)


llm_analysis_dag()
