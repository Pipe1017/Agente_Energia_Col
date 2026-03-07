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

# Agentes activos: se leen dinámicamente de la BD en load_market_context


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
            result = conn.execute(query)
            df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))

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

        # Leer agentes activos desde la BD (evitar lista hardcodeada)
        with engine.connect() as conn:
            agent_rows = conn.execute(text("SELECT sic_code FROM agents ORDER BY sic_code")).fetchall()
        context["active_agents"] = [r[0] for r in agent_rows] or ["EPMC"]

        logger.info("Contexto de mercado cargado: precio=%.2f COP | hidro=%.1f%% | agentes=%s",
                    context["spot_price_cop"], context["hydrology_pct"], context["active_agents"])
        return context

    @task(task_id="load_champion_and_predict")
    def load_champion_and_predict(market_context: dict) -> dict:
        """
        Carga el modelo champion desde MLflow y genera predicciones 24h.
        Lee 200h de historial real desde market_data para calcular lag features
        correctamente (lag_24h, lag_168h, rolling windows).
        Persiste las predicciones en la tabla predictions por cada agente activo.
        """
        import sys, os, tempfile, uuid, json
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")
        from dags._utils import get_mlflow_client, get_db_engine
        from sqlalchemy import text

        if not market_context:
            return {}

        MODEL_NAME = "xgboost_price_predictor"
        client = get_mlflow_client()

        try:
            versions = client.get_latest_versions(MODEL_NAME, ["Production"])
        except Exception as exc:
            logger.warning("Sin champion en MLflow: %s — omitiendo predicción", exc)
            return {}

        if not versions:
            logger.warning("Sin champion disponible en MLflow — omitiendo predicción")
            return {}

        mv = versions[0]
        tags = mv.tags or {}
        model_metrics = {
            k.removeprefix("metric."): float(v)
            for k, v in tags.items()
            if k.startswith("metric.")
        }
        model_version = mv.version
        # UUID de dominio del modelo (guardado como tag en save_to_registry)
        domain_model_id = tags.get("domain_id", str(uuid.uuid4()))

        import mlflow
        tmpdir = tempfile.mkdtemp(prefix="champion_")
        run_id = mv.run_id
        local_path = mlflow.artifacts.download_artifacts(
            artifact_uri=f"runs:/{run_id}/full_model",
            dst_path=tmpdir,
        )

        from models.price_prediction.xgboost_model import XGBoostPriceModel
        from pathlib import Path
        import pandas as pd
        import numpy as np
        from datetime import datetime, timezone, timedelta
        from features.feature_pipeline import build_feature_matrix, PRICE_PREDICTION_FEATURES

        model = XGBoostPriceModel.load(Path(local_path))

        # --- Cargar 200h de historial real desde market_data ---
        # Esto permite calcular lag_24h y lag_168h correctamente
        engine = get_db_engine()
        with engine.connect() as conn:
            hist_rows = conn.execute(text("""
                SELECT timestamp, spot_price_cop, demand_mwh,
                       hydrology_pct, reservoir_level_pct, thermal_dispatch_pct
                FROM market_data
                WHERE agent_sic_code IS NULL
                ORDER BY timestamp DESC
                LIMIT 210
            """)).fetchall()

        if not hist_rows:
            logger.warning("Sin datos históricos en market_data — omitiendo predicción")
            return {}

        hist_df = pd.DataFrame(hist_rows, columns=[
            "timestamp", "spot_price_cop", "demand_mwh",
            "hydrology_pct", "reservoir_level_pct", "thermal_dispatch_pct",
        ])
        hist_df = hist_df.sort_values("timestamp").reset_index(drop=True)
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])

        # Escalar hidro/embalse si están como fracción (0-1) en lugar de porcentaje
        if hist_df["hydrology_pct"].max() <= 3.0:
            hist_df["hydrology_pct"] *= 100.0
        if hist_df["reservoir_level_pct"].max() <= 1.0:
            hist_df["reservoir_level_pct"] *= 100.0

        # --- Construir filas futuras (próximas 24 horas) ---
        latest_ts = hist_df["timestamp"].iloc[-1]
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.tz_localize("UTC")
        future_timestamps = [latest_ts + timedelta(hours=h) for h in range(1, 25)]

        latest = hist_df.iloc[-1]
        future_rows = pd.DataFrame([{
            "timestamp": ts,
            "spot_price_cop": float(latest["spot_price_cop"]),
            "demand_mwh": float(latest["demand_mwh"]),
            "hydrology_pct": float(latest["hydrology_pct"]),
            "reservoir_level_pct": float(latest["reservoir_level_pct"]),
            "thermal_dispatch_pct": float(latest["thermal_dispatch_pct"]),
        } for ts in future_timestamps])

        combined = pd.concat([hist_df, future_rows], ignore_index=True)
        combined["timestamp"] = pd.to_datetime(combined["timestamp"])

        feature_df = build_feature_matrix(combined, drop_na=False)
        future_features = feature_df[feature_df["timestamp"].isin(future_timestamps)].copy()
        future_features = future_features.dropna(subset=PRICE_PREDICTION_FEATURES[:10])

        if future_features.empty:
            logger.warning("No hay features válidas para predicción futura")
            return {}

        # Imputar NaN restantes con 0 para features opcionales
        for feat in PRICE_PREDICTION_FEATURES:
            if feat not in future_features.columns:
                future_features[feat] = 0.0
        future_features[PRICE_PREDICTION_FEATURES] = (
            future_features[PRICE_PREDICTION_FEATURES].fillna(0.0)
        )

        X = future_features[PRICE_PREDICTION_FEATURES]
        preds, lower, upper = model.predict_with_intervals(X)

        predictions = []
        for i, ts in enumerate(future_features["timestamp"]):
            h = pd.to_datetime(ts).hour
            predictions.append({
                # Formato esperado por pg_prediction_repository._hourly_to_domain
                "target_hour": str(ts),
                "predicted_cop": float(preds[i]),
                "lower_bound_cop": float(lower[i]),
                "upper_bound_cop": float(upper[i]),
                "confidence": 0.7,
                "is_peak_hour": 18 <= h < 21,
                # Alias para uso en llm prompt (no se persiste por separado)
                "predicted_price": float(preds[i]),
                "lower_bound": float(lower[i]),
                "upper_bound": float(upper[i]),
                "timestamp": str(ts),
            })

        avg_pred = float(np.mean([p["predicted_price"] for p in predictions]))
        logger.info("Predicciones generadas: %d horas | prom=%.2f COP", len(predictions), avg_pred)

        # --- Persistir predicciones en tabla predictions por agente ---
        active_agents = market_context.get("active_agents", [])
        now = datetime.now(timezone.utc)

        if active_agents:
            hourly_json = json.dumps(predictions)
            with engine.begin() as conn:
                for agent_sic in active_agents:
                    conn.execute(text("""
                        INSERT INTO predictions
                            (id, agent_sic_code, generated_at, model_version_id,
                             horizon_hours, hourly_predictions, actuals, overall_confidence)
                        VALUES
                            (:id::uuid, :sic, :generated_at, :model_id::uuid,
                             24, CAST(:hourly AS json), CAST('[]' AS json), :confidence)
                    """), {
                        "id": str(uuid.uuid4()),
                        "sic": agent_sic,
                        "generated_at": now,
                        "model_id": domain_model_id,
                        "hourly": hourly_json,
                        "confidence": 0.7,
                    })
            logger.info("Predicciones guardadas para %d agentes", len(active_agents))

        return {
            "predictions": predictions,
            "model_version": model_version,
            "model_metrics": model_metrics,
            "domain_model_id": domain_model_id,
        }

    def _call_llm_for_agent(market_context: dict, prediction_result: dict, agent_sic_code: str) -> dict:
        """Helper interno (no task): llama al LLM para un agente y retorna la recomendación."""
        """
        Construye prompt estructurado y llama a Deepseek para generar
        la recomendación de precio oferta para el agente.
        """
        import sys, os, json
        sys.path.insert(0, "/opt/airflow")

        if not market_context or not prediction_result.get("predictions"):
            logger.warning("Sin contexto o predicciones para %s", agent_sic_code)
            return {}

        # Seleccionar proveedor LLM según LLM_PROVIDER
        llm_provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()

        if llm_provider == "ollama":
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                format="json",
                temperature=0.3,
            )
            llm_model_name = f"ollama:{os.environ.get('OLLAMA_MODEL', 'llama3.2')}"
        else:
            from langchain_openai import ChatOpenAI
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key and llm_provider == "deepseek":
                raise ValueError("DEEPSEEK_API_KEY no configurado")
            base_url = (os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
                        if llm_provider == "deepseek" else None)
            model_id = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
            llm = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_id,
                temperature=0.3,
                max_tokens=800,
                model_kwargs={"response_format": {"type": "json_object"}},
            )
            llm_model_name = f"{llm_provider}:{model_id}"

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

        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])

            content = response.content if hasattr(response, "content") else str(response)
            recommendation = json.loads(content)
            recommendation["agent_sic_code"] = agent_sic_code
            recommendation["model_version"] = prediction_result.get("model_version")
            recommendation["llm_model_used"] = llm_model_name
            recommendation["predictions_summary"] = {
                "avg_price": avg_pred,
                "avg_peak_price": avg_peak,
                "horizon_hours": len(predictions),
            }

            logger.info("Recomendación generada para %s via %s: %.2f COP/kWh | riesgo=%s",
                        agent_sic_code, llm_model_name,
                        recommendation.get("recommended_offer_price_cop", 0),
                        recommendation.get("risk_level", "?"))
            return recommendation

        except json.JSONDecodeError as e:
            logger.error("LLM no retornó JSON válido para %s: %s", agent_sic_code, e)
            return {}
        except Exception as e:
            logger.error("Error llamando LLM (%s) para %s: %s", llm_model_name, agent_sic_code, e)
            raise

    @task(task_id="generate_and_store_recommendations")
    def generate_and_store_recommendations(
        market_context: dict,
        prediction_result: dict,
    ) -> dict:
        """
        Itera sobre todos los agentes activos (leídos desde la BD),
        llama al LLM para cada uno y persiste las recomendaciones en PostgreSQL.
        Un único task evita los límites de XCom y el parseo dinámico de Airflow.
        """
        import sys, uuid, json
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from datetime import datetime, timezone
        from sqlalchemy import text

        active_agents = market_context.get("active_agents", ["EPMC"])
        logger.info("Generando recomendaciones para %d agentes: %s", len(active_agents), active_agents)

        stored = 0
        engine = get_db_engine()
        now = datetime.now(timezone.utc)

        for agent_sic_code in active_agents:
            try:
                rec = _call_llm_for_agent(market_context, prediction_result, agent_sic_code)
                if not rec or not rec.get("recommended_offer_price_cop"):
                    logger.warning("Sin recomendación válida para %s", agent_sic_code)
                    continue

                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO recommendations
                            (id, agent_sic_code, prediction_id, model_version_id,
                             risk_level, narrative, key_factors, hourly_offers,
                             llm_model_used, generated_at)
                        VALUES
                            (:id, :sic, NULL, NULL,
                             :risk, :narrative, CAST(:key_factors AS json), CAST(:hourly_offers AS json),
                             :llm_model, :generated_at)
                        ON CONFLICT DO NOTHING
                    """), {
                        "id": str(uuid.uuid4()),
                        "sic": agent_sic_code,
                        "risk": rec.get("risk_level", "medium"),
                        "narrative": rec.get("rationale", ""),
                        "key_factors": json.dumps(rec.get("key_factors", [])),
                        "hourly_offers": json.dumps(rec.get("hourly_strategy", {})),
                        "llm_model": rec.get("llm_model_used", "deepseek-chat"),
                        "generated_at": now,
                    })
                stored += 1
                logger.info("Recomendación almacenada para %s", agent_sic_code)

            except Exception as exc:
                logger.error("Error procesando agente %s: %s", agent_sic_code, exc)

        logger.info("Total recomendaciones almacenadas: %d / %d", stored, len(active_agents))
        return {"stored": stored, "agents": active_agents}

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    market_ctx = load_market_context()
    prediction = load_champion_and_predict(market_ctx)
    generate_and_store_recommendations(market_ctx, prediction)


llm_analysis_dag()
