"""
DAG: xm_ingestion
Schedule: cada hora

Descarga datos del mercado eléctrico colombiano desde la API de XM
y los almacena en PostgreSQL (tabla market_data).

Métricas descargadas:
  - PrecioMercado       (horario)  → spot_price_cop
  - DemandaComercial    (horario)  → demand_mwh
  - AportesHidro        (diario)   → hydrology_pct
  - NivelEmbalse        (diario)   → reservoir_level_pct
  - GeneracionTermica   (horario)  → thermal_dispatch_pct (calculado)

Los últimos 2 días se re-descargan siempre (idempotente por UPSERT).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import pendulum
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


@dag(
    dag_id="xm_ingestion",
    schedule="@hourly",
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["xm", "ingestion", "mercado"],
    doc_md=__doc__,
)
def xm_ingestion_dag():

    @task(task_id="fetch_spot_prices", retries=3)
    def fetch_spot_prices() -> dict:
        """Descarga precio bolsa nacional horario desde SINERGOX."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_hourly

        start, end = fetch_date_range(lookback_days=2)
        logger.info("Descargando PrecioMercado %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("PrecioMercado", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("PrecioMercado retornó datos vacíos")
                return {}

            # pydataxm devuelve columna con el nombre de la métrica
            value_col = [c for c in df.columns if c not in ("Date", "Hour", "Values")][0] \
                if "Values" not in df.columns else "Values"
            result = xm_df_to_hourly(df, value_col=value_col)
            logger.info("Precios descargados: %d registros", len(result))
            # XCom solo acepta JSON → convertir timestamps a strings
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando PrecioMercado: %s", e)
            raise

    @task(task_id="fetch_demand", retries=3)
    def fetch_demand() -> dict:
        """Descarga demanda comercial SIN horaria."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_hourly

        start, end = fetch_date_range(lookback_days=2)
        logger.info("Descargando DemandaComercial %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("DemandaComercial", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("DemandaComercial retornó vacío")
                return {}

            value_col = [c for c in df.columns if c not in ("Date", "Hour")][0]
            result = xm_df_to_hourly(df, value_col=value_col)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando DemandaComercial: %s", e)
            raise

    @task(task_id="fetch_hydrology", retries=3)
    def fetch_hydrology() -> dict:
        """Descarga aportes hidrológicos diarios (% vs histórico)."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_daily

        start, end = fetch_date_range(lookback_days=3)
        logger.info("Descargando AportesHidro %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("AportesHidro", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("AportesHidro retornó vacío")
                return {}

            value_col = [c for c in df.columns if c not in ("Date",)][0]
            result = xm_df_to_daily(df, value_col=value_col)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando AportesHidro: %s", e)
            raise

    @task(task_id="fetch_reservoir", retries=3)
    def fetch_reservoir() -> dict:
        """Descarga nivel de embalses del sistema (%) diario."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_daily

        start, end = fetch_date_range(lookback_days=3)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("NivelEmbalse", "Sistema", start, end)

            if df is None or df.empty:
                return {}

            value_col = [c for c in df.columns if c not in ("Date",)][0]
            result = xm_df_to_daily(df, value_col=value_col)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando NivelEmbalse: %s", e)
            raise

    @task(task_id="fetch_thermal_generation", retries=3)
    def fetch_thermal_generation() -> dict:
        """Descarga generación térmica horaria para calcular % del despacho."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_hourly

        start, end = fetch_date_range(lookback_days=2)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("GeneracionTermica", "Sistema", start, end)

            if df is None or df.empty:
                return {}

            value_col = [c for c in df.columns if c not in ("Date", "Hour")][0]
            result = xm_df_to_hourly(df, value_col=value_col)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando GeneracionTermica: %s", e)
            return {}   # No crítico — continuar sin esta métrica

    @task(task_id="store_to_db")
    def store_to_db(
        prices: dict,
        demand: dict,
        hydrology: dict,
        reservoir: dict,
        thermal: dict,
    ) -> dict:
        """
        Merge de todas las métricas → upsert en PostgreSQL market_data.
        La operación es idempotente: UPSERT por (timestamp, agent_sic_code).
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range

        import pandas as pd
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        engine = __import__("dags._utils", fromlist=["get_db_engine"]).get_db_engine()

        if not prices:
            logger.warning("Sin datos de precio — abortando store_to_db")
            return {"records_inserted": 0}

        # Construir DataFrame unificado por hora
        rows = []
        for ts_str, price in prices.items():
            ts = pd.Timestamp(ts_str)

            hydro_val = hydrology.get(str(ts.date()), 85.0)       # fallback histórico
            reservoir_val = reservoir.get(str(ts.date()), 55.0)
            demand_val = demand.get(ts_str, None)
            thermal_val = thermal.get(ts_str, None)

            if demand_val is None:
                continue  # sin demanda no tiene sentido el registro

            total_gen = demand_val if demand_val > 0 else 1
            thermal_pct = min((thermal_val / total_gen) * 100, 100) if thermal_val else 15.0

            rows.append({
                "id": str(uuid.uuid4()),
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "spot_price_cop": price,
                "demand_mwh": demand_val,
                "hydrology_pct": hydro_val,
                "reservoir_level_pct": reservoir_val,
                "thermal_dispatch_pct": thermal_pct,
                "agent_sic_code": None,
                "ingested_at": datetime.now(timezone.utc),
            })

        if not rows:
            return {"records_inserted": 0}

        from sqlalchemy import text
        with engine.begin() as conn:
            # UPSERT: en conflicto de timestamp actualizar valores
            stmt = text("""
                INSERT INTO market_data
                    (id, timestamp, spot_price_cop, demand_mwh, hydrology_pct,
                     reservoir_level_pct, thermal_dispatch_pct, agent_sic_code, ingested_at)
                VALUES
                    (:id, :timestamp, :spot_price_cop, :demand_mwh, :hydrology_pct,
                     :reservoir_level_pct, :thermal_dispatch_pct, :agent_sic_code, :ingested_at)
                ON CONFLICT (timestamp, agent_sic_code)
                DO UPDATE SET
                    spot_price_cop      = EXCLUDED.spot_price_cop,
                    demand_mwh          = EXCLUDED.demand_mwh,
                    hydrology_pct       = EXCLUDED.hydrology_pct,
                    reservoir_level_pct = EXCLUDED.reservoir_level_pct,
                    thermal_dispatch_pct = EXCLUDED.thermal_dispatch_pct,
                    ingested_at         = EXCLUDED.ingested_at
            """)
            conn.execute(stmt, rows)

        logger.info("Upsert completado: %d registros", len(rows))
        return {"records_inserted": len(rows), "date_range": [str(min(prices)), str(max(prices))]}

    @task(task_id="store_raw_to_minio")
    def store_raw_to_minio(prices: dict, demand: dict) -> str:
        """Guarda copia del raw data en MinIO como parquet para trazabilidad."""
        import sys, io, tempfile
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_minio_client

        import pandas as pd
        from datetime import datetime, timezone

        if not prices:
            return ""

        df = pd.DataFrame([
            {"timestamp": ts, "spot_price_cop": v, "demand_mwh": demand.get(ts)}
            for ts, v in prices.items()
        ])

        now = datetime.now(timezone.utc)
        object_name = f"{now.year}/{now.month:02d}/{now.day:02d}/{now.hour:02d}/market.parquet"

        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            df.to_parquet(tmp.name, index=False)
            client = get_minio_client()
            if not client.bucket_exists("raw-data"):
                client.make_bucket("raw-data")
            client.fput_object("raw-data", object_name, tmp.name)

        logger.info("Raw data guardado: raw-data/%s", object_name)
        return f"raw-data/{object_name}"

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    prices_data = fetch_spot_prices()
    demand_data = fetch_demand()
    hydro_data = fetch_hydrology()
    reservoir_data = fetch_reservoir()
    thermal_data = fetch_thermal_generation()

    result = store_to_db(
        prices=prices_data,
        demand=demand_data,
        hydrology=hydro_data,
        reservoir=reservoir_data,
        thermal=thermal_data,
    )

    store_raw_to_minio(prices=prices_data, demand=demand_data)


xm_ingestion_dag()
