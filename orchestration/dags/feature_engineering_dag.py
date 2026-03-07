"""
DAG: feature_engineering
Schedule: cada 2 horas (ligeramente después de xm_ingestion)

Lee market_data de PostgreSQL, construye la feature matrix completa
con la misma lógica de ml/features/feature_pipeline.py y la persiste en:
  - PostgreSQL: tabla features_cache (reemplaza por rango de fechas)
  - MinIO:      features/{year}/{month}/{day}/features.parquet

El DAG es idempotente: siempre re-genera los últimos 7 días de features.

Lookback de market_data: 400 días (suficiente para calcular correctamente
las ventanas largas de 30d y 90d de hidrología y el percentil anual de precio).
La salida a features_cache solo contiene los últimos 7 días para no re-procesar
historial innecesariamente (el historial antiguo ya fue computado antes).
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

# Cuánto historial necesitamos para computar correctamente las ventanas largas
# price_percentile_365d → 365d, hydrology_rolling_mean_90d → 90d
# + 7d buffer de salida = 400d total
FEATURE_LOOKBACK_DAYS = 400

# Solo persiste features de los últimos N días (el resto ya estaba en cache)
OUTPUT_DAYS = 7


@dag(
    dag_id="feature_engineering",
    schedule="15 */2 * * *",   # cada 2h a los :15 minutos
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["features", "ml", "engineering"],
    doc_md=__doc__,
)
def feature_engineering_dag():

    @task(task_id="compute_features")
    def compute_features() -> dict:
        """
        Carga market_data de los últimos FEATURE_LOOKBACK_DAYS días,
        construye features (incluyendo ventanas largas de hidrología y
        percentiles de precio), y retorna solo los últimos OUTPUT_DAYS
        para persistir en features_cache.

        La carga de market_data se hace internamente (no via XCom) para
        evitar serializar cientos de MB entre tasks.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")
        from dags._utils import get_db_engine
        from datetime import date, timedelta

        import pandas as pd
        from sqlalchemy import text
        from features.feature_pipeline import build_feature_matrix

        end_date = date.today()
        start_date = end_date - timedelta(days=FEATURE_LOOKBACK_DAYS)
        output_cutoff = end_date - timedelta(days=OUTPUT_DAYS)

        logger.info(
            "Cargando market_data %s → %s (lookback=%d días)",
            start_date, end_date, FEATURE_LOOKBACK_DAYS,
        )

        engine = get_db_engine()
        query = text("""
            SELECT
                timestamp, spot_price_cop, demand_mwh,
                hydrology_pct, reservoir_level_pct, thermal_dispatch_pct,
                precio_escasez_cop, gen_hidraulica_gwh, gen_termica_gwh,
                gen_solar_gwh, gen_eolica_gwh
            FROM market_data
            WHERE timestamp >= :start AND timestamp <= :end
              AND agent_sic_code IS NULL
            ORDER BY timestamp ASC
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"start": str(start_date), "end": str(end_date)})
            df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))

        if df.empty:
            logger.warning(
                "No hay datos en market_data para %s → %s", start_date, end_date
            )
            return {"rows": 0}

        logger.info("market_data cargados: %d filas", len(df))
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Construir features (incluye validate_and_clean internamente)
        feature_df = build_feature_matrix(df, drop_na=True)

        if feature_df.empty:
            logger.warning(
                "build_feature_matrix retornó vacío — posiblemente datos "
                "insuficientes para los lags de 168h"
            )
            return {"rows": 0}

        logger.info(
            "Features construidas: %d filas × %d columnas", *feature_df.shape
        )

        # Filtrar a solo los últimos OUTPUT_DAYS (no re-procesar historial)
        output_df = feature_df[
            feature_df["timestamp"] >= pd.Timestamp(output_cutoff, tz="UTC")
        ].copy()

        # Si no hay filas con tz-aware, intentar sin tz
        if output_df.empty:
            output_df = feature_df[
                feature_df["timestamp"].dt.date >= output_cutoff
            ].copy()

        logger.info(
            "Últimos %d días: %d filas para persistir", OUTPUT_DAYS, len(output_df)
        )

        output_df["timestamp"] = output_df["timestamp"].astype(str)
        return {"data": output_df.to_dict(orient="records"), "rows": len(output_df)}

    @task(task_id="store_features_db")
    def store_features_db(feature_payload: dict) -> int:
        """
        Persiste features en PostgreSQL (tabla features_cache).
        UPSERT por timestamp para idempotencia.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")
        from dags._utils import get_db_engine

        if not feature_payload.get("data"):
            logger.info("Sin features nuevas para persistir en BD")
            return 0

        import json
        import uuid
        import pandas as pd
        from sqlalchemy import text

        df = pd.DataFrame(feature_payload["data"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        engine = get_db_engine()
        rows = df.to_dict(orient="records")

        # Columnas de features (excluir timestamp y target)
        numeric_cols = [c for c in df.columns if c not in ("timestamp", "spot_price_cop")]

        with engine.begin() as conn:
            for row in rows:
                ts = row["timestamp"]
                features_json = {
                    k: (None if (v is None or (isinstance(v, float) and v != v)) else float(v))
                    for k, v in row.items()
                    if k not in ("timestamp", "spot_price_cop")
                }
                target = row.get("spot_price_cop")
                if target is not None:
                    target = float(target)

                conn.execute(text("""
                    INSERT INTO features_cache (id, timestamp, features_json, target_price)
                    VALUES (:id, :ts, CAST(:features AS json), :target)
                    ON CONFLICT (timestamp)
                    DO UPDATE SET
                        features_json = EXCLUDED.features_json,
                        target_price  = EXCLUDED.target_price,
                        updated_at    = NOW()
                """), {
                    "id": str(uuid.uuid4()),
                    "ts": ts,
                    "features": json.dumps(features_json),
                    "target": target,
                })

        logger.info("features_cache actualizado: %d filas", len(rows))
        return len(rows)

    @task(task_id="store_features_minio")
    def store_features_minio(feature_payload: dict) -> str:
        """
        Persiste features en MinIO como parquet para reproducibilidad.
        Ruta: features/{year}/{month}/{day}/features.parquet
        """
        import sys, tempfile
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_minio_client
        from datetime import datetime, timezone

        if not feature_payload.get("data"):
            return ""

        import pandas as pd

        df = pd.DataFrame(feature_payload["data"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        now = datetime.now(timezone.utc)
        object_name = f"{now.year}/{now.month:02d}/{now.day:02d}/features.parquet"

        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            df.to_parquet(tmp.name, index=False)
            client = get_minio_client()
            if not client.bucket_exists("features"):
                client.make_bucket("features")
            client.fput_object("features", object_name, tmp.name)

        logger.info("Features guardadas en MinIO: features/%s", object_name)
        return f"features/{object_name}"

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    feature_payload = compute_features()
    store_features_db(feature_payload)
    store_features_minio(feature_payload)


feature_engineering_dag()
