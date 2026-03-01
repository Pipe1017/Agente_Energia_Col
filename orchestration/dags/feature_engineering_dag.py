"""
DAG: feature_engineering
Schedule: cada 2 horas (ligeramente después de xm_ingestion)

Lee market_data de PostgreSQL, construye la feature matrix completa
con la misma lógica de ml/features/feature_pipeline.py y la persiste en:
  - PostgreSQL: tabla features_cache (reemplaza por rango de fechas)
  - MinIO:      features/{year}/{month}/{day}/features.parquet

El DAG es idempotente: siempre re-genera los últimos 7 días.
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

    @task(task_id="load_market_data")
    def load_market_data() -> dict:
        """
        Carga market_data de PostgreSQL para los últimos 7 días + buffer
        para que los lags (168h) estén disponibles.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine, fetch_date_range
        from datetime import timedelta

        start, end = fetch_date_range(lookback_days=14)  # 14d para lags 168h
        logger.info("Cargando market_data %s → %s", start, end)

        import pandas as pd
        from sqlalchemy import text

        engine = get_db_engine()
        query = text("""
            SELECT
                timestamp, spot_price_cop, demand_mwh,
                hydrology_pct, reservoir_level_pct, thermal_dispatch_pct
            FROM market_data
            WHERE timestamp >= :start AND timestamp <= :end
              AND agent_sic_code IS NULL
            ORDER BY timestamp ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"start": str(start), "end": str(end)})

        if df.empty:
            logger.warning("No hay datos en market_data para el rango %s → %s", start, end)
            return {"rows": 0}

        logger.info("market_data cargados: %d filas", len(df))
        # Serializar para XCom (JSON)
        df["timestamp"] = df["timestamp"].astype(str)
        return {"data": df.to_dict(orient="records"), "rows": len(df)}

    @task(task_id="build_features")
    def build_features(market_payload: dict) -> dict:
        """
        Construye la feature matrix completa usando feature_pipeline.py.
        Retorna solo los últimos 7 días (sin el buffer de lags).
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")

        if not market_payload.get("data"):
            logger.warning("Sin datos de mercado — omitiendo build_features")
            return {"rows": 0}

        import pandas as pd
        from features.feature_pipeline import build_feature_matrix

        df = pd.DataFrame(market_payload["data"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        logger.info("Construyendo features para %d filas...", len(df))
        feature_df = build_feature_matrix(df, drop_na=True)

        if feature_df.empty:
            logger.warning("build_feature_matrix retornó vacío")
            return {"rows": 0}

        # Mantener solo últimos 7 días (no el buffer de lags)
        cutoff = feature_df["timestamp"].max() - pd.Timedelta(days=7)
        feature_df = feature_df[feature_df["timestamp"] >= cutoff].copy()

        logger.info("Features construidas: %d filas, %d columnas", *feature_df.shape)
        feature_df["timestamp"] = feature_df["timestamp"].astype(str)
        return {"data": feature_df.to_dict(orient="records"), "rows": len(feature_df)}

    @task(task_id="store_features_db")
    def store_features_db(feature_payload: dict) -> int:
        """
        Persiste features en PostgreSQL (tabla features_cache).
        UPSERT por timestamp para idempotencia.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine

        if not feature_payload.get("data"):
            return 0

        import pandas as pd
        from sqlalchemy import text

        df = pd.DataFrame(feature_payload["data"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        engine = get_db_engine()
        rows = df.to_dict(orient="records")

        # Columnas de features numéricas (excluir timestamp y target)
        numeric_cols = [c for c in df.columns if c not in ("timestamp", "spot_price_cop")]

        with engine.begin() as conn:
            for row in rows:
                ts = row["timestamp"]
                features_json = {k: row[k] for k in numeric_cols if k in row}
                target = row.get("spot_price_cop")

                conn.execute(text("""
                    INSERT INTO features_cache (timestamp, features_json, target_price)
                    VALUES (:ts, :features::jsonb, :target)
                    ON CONFLICT (timestamp)
                    DO UPDATE SET
                        features_json = EXCLUDED.features_json,
                        target_price  = EXCLUDED.target_price,
                        updated_at    = NOW()
                """), {"ts": ts, "features": __import__("json").dumps(features_json), "target": target})

        logger.info("features_cache actualizado: %d filas", len(rows))
        return len(rows)

    @task(task_id="store_features_minio")
    def store_features_minio(feature_payload: dict) -> str:
        """
        Persiste features en MinIO como parquet para reproducibilidad de entrenamientos.
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
        object_name = (
            f"{now.year}/{now.month:02d}/{now.day:02d}/features.parquet"
        )

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
    market_payload = load_market_data()
    feature_payload = build_features(market_payload)

    store_features_db(feature_payload)
    store_features_minio(feature_payload)


feature_engineering_dag()
