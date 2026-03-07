"""
DAG: xm_ingestion
Schedule: cada hora

Descarga datos del mercado eléctrico colombiano desde la API de XM
y los almacena en PostgreSQL (tabla market_data).

Métricas descargadas (SINERGOX vía pydataxm.ReadDB):
  - PrecBolsNaci       (horario)  → spot_price_cop
  - DemaReal           (horario)  → demand_mwh
  - PorcApor           (diario)   → hydrology_pct
  - PorcVoluUtilDiar   (diario)   → reservoir_level_pct
  - Gene               (horario)  → thermal_dispatch_pct (calculado)
  - PrecEsca           (diario)   → precio_escasez_cop

Métricas descargadas (SIMEM vía pydataxm.ReadSIMEM — Dataset E17D25):
  - Generación real por tecnología → gen_hidraulica_gwh, gen_termica_gwh,
                                     gen_solar_gwh, gen_eolica_gwh

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
        logger.info("Descargando PrecBolsNaci %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("PrecBolsNaci", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("PrecBolsNaci retornó datos vacíos")
                return {}

            result = xm_df_to_hourly(df)
            logger.info("Precios descargados: %d registros", len(result))
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando PrecBolsNaci: %s", e)
            raise

    @task(task_id="fetch_demand", retries=3)
    def fetch_demand() -> dict:
        """Descarga demanda comercial SIN horaria."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_hourly

        start, end = fetch_date_range(lookback_days=2)
        logger.info("Descargando DemaReal %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("DemaReal", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("DemaReal retornó vacío")
                return {}

            result = xm_df_to_hourly(df)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando DemaReal: %s", e)
            raise

    @task(task_id="fetch_hydrology", retries=3)
    def fetch_hydrology() -> dict:
        """Descarga aportes hidrológicos diarios (% vs histórico)."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_daily

        start, end = fetch_date_range(lookback_days=5)
        logger.info("Descargando PorcApor %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("PorcApor", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("PorcApor retornó vacío")
                return {}

            result = xm_df_to_daily(df)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando PorcApor: %s", e)
            raise

    @task(task_id="fetch_reservoir", retries=3)
    def fetch_reservoir() -> dict:
        """Descarga nivel de embalses del sistema (%) diario."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_daily

        start, end = fetch_date_range(lookback_days=5)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("PorcVoluUtilDiar", "Sistema", start, end)

            if df is None or df.empty:
                return {}

            result = xm_df_to_daily(df)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando PorcVoluUtilDiar: %s", e)
            raise

    @task(task_id="fetch_thermal_generation", retries=3)
    def fetch_thermal_generation() -> dict:
        """Descarga generación total horaria para calcular % del despacho."""
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_hourly

        start, end = fetch_date_range(lookback_days=2)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("Gene", "Sistema", start, end)

            if df is None or df.empty:
                return {}

            result = xm_df_to_hourly(df)
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando Gene: %s", e)
            return {}   # No crítico — continuar sin esta métrica

    @task(task_id="fetch_escasez_price", retries=3)
    def fetch_escasez_price() -> dict:
        """
        Descarga el Precio de Escasez de Activación (PrecEsca) diario.
        Es el precio regulado por CREG que define si el recurso de escasez
        se activa — señal política crítica para el mercado (~590 COP/kWh).
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range, xm_df_to_daily

        start, end = fetch_date_range(lookback_days=5)
        logger.info("Descargando PrecEsca %s → %s", start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data("PrecEsca", "Sistema", start, end)

            if df is None or df.empty:
                logger.warning("PrecEsca retornó vacío")
                return {}

            result = xm_df_to_daily(df)
            logger.info("PrecEsca descargado: %d días", len(result))
            return {str(k): v for k, v in result.items()}

        except Exception as e:
            logger.error("Error descargando PrecEsca: %s", e)
            return {}   # No crítico — precio de escasez cambia mensualmente

    @task(task_id="fetch_generation_by_type", retries=3)
    def fetch_generation_by_type() -> dict:
        """
        Descarga generación real por tipo de tecnología desde SIMEM (Dataset E17D25).
        Retorna dict {date_str: {hidraulica: GWh, termica: GWh, solar: GWh, eolica: GWh}}.

        El Ratio_Termico = Termica / (Hidraulica + 1) es el driver más importante
        del precio según el análisis exploratorio del notebook.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import fetch_date_range

        import pandas as pd

        start, end = fetch_date_range(lookback_days=5)
        logger.info("Descargando generación por tipo SIMEM E17D25 %s → %s", start, end)

        try:
            from pydataxm.pydatasimem import ReadSIMEM
            # ReadSIMEM es un dataclass: se instancia con (dataset_id, start, end)
            api = ReadSIMEM("E17D25", str(start), str(end))
            df = api.main()

            if df is None or df.empty:
                logger.warning("SIMEM E17D25 retornó vacío")
                return {}

            logger.info("E17D25: %d filas, cols=%s", len(df), list(df.columns))

            # E17D25 columnas confirmadas: Fecha, TipoGeneracion, GeneracionRealEstimada (kWh)
            # Agrupar por Fecha + TipoGeneracion y sumar toda la generación del país
            gen = (
                df.groupby(["Fecha", "TipoGeneracion"])["GeneracionRealEstimada"]
                .sum()
                .reset_index()
            )

            # Mapeo directo a campos del modelo (SIMEM usa nombres en español sin tilde)
            TYPE_MAP = {
                "Hidraulica": "hidraulica",
                "Termica": "termica",
                "Solar": "solar",
                "Eolica": "eolica",
                "Cogenerador": "termica",   # cogeneración = térmica distribuida
            }

            result: dict[str, dict] = {}
            KWH_TO_GWH = 1_000_000.0  # GeneracionRealEstimada está en kWh

            for _, row in gen.iterrows():
                date_str = str(pd.Timestamp(str(row["Fecha"])).date())
                tipo = TYPE_MAP.get(row["TipoGeneracion"])
                if tipo is None:
                    continue
                val_gwh = float(row["GeneracionRealEstimada"]) / KWH_TO_GWH

                if date_str not in result:
                    result[date_str] = {"hidraulica": 0.0, "termica": 0.0, "solar": 0.0, "eolica": 0.0}
                result[date_str][tipo] = result[date_str].get(tipo, 0.0) + val_gwh

            logger.info("Generación por tipo SIMEM: %d días", len(result))
            return result

        except Exception as e:
            logger.error("Error descargando generación por tipo SIMEM: %s", e)
            return {}   # No crítico

    @task(task_id="store_to_db")
    def store_to_db(
        prices: dict,
        demand: dict,
        hydrology: dict,
        reservoir: dict,
        thermal: dict,
        escasez: dict,
        gen_by_type: dict,
    ) -> dict:
        """
        Merge de todas las métricas → upsert en PostgreSQL market_data.
        La operación es idempotente: UPSERT por (timestamp, agent_sic_code).
        """
        import sys
        sys.path.insert(0, "/opt/airflow")

        import pandas as pd
        from sqlalchemy import text

        engine = __import__("dags._utils", fromlist=["get_db_engine"]).get_db_engine()

        if not prices:
            logger.warning("Sin datos de precio — abortando store_to_db")
            return {"records_inserted": 0}

        rows = []
        for ts_str, price in prices.items():
            ts = pd.Timestamp(ts_str)
            date_str = str(ts.date())

            hydro_val = hydrology.get(date_str, 85.0)
            reservoir_val = reservoir.get(date_str, 55.0)
            demand_val = demand.get(ts_str, None)
            thermal_val = thermal.get(ts_str, None)
            escasez_val = escasez.get(date_str, None)

            # Generación por tipo del día
            gen_day = gen_by_type.get(date_str, {})
            hidro_gwh = gen_day.get("hidraulica", None)
            term_gwh = gen_day.get("termica", None)
            solar_gwh = gen_day.get("solar", None)
            eol_gwh = gen_day.get("eolica", None)

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
                "precio_escasez_cop": escasez_val,
                "gen_hidraulica_gwh": hidro_gwh,
                "gen_termica_gwh": term_gwh,
                "gen_solar_gwh": solar_gwh,
                "gen_eolica_gwh": eol_gwh,
                "agent_sic_code": None,
                "ingested_at": datetime.now(timezone.utc),
            })

        if not rows:
            return {"records_inserted": 0}

        with engine.begin() as conn:
            stmt = text("""
                INSERT INTO market_data
                    (id, timestamp, spot_price_cop, demand_mwh, hydrology_pct,
                     reservoir_level_pct, thermal_dispatch_pct,
                     precio_escasez_cop, gen_hidraulica_gwh, gen_termica_gwh,
                     gen_solar_gwh, gen_eolica_gwh,
                     agent_sic_code, ingested_at)
                VALUES
                    (:id, :timestamp, :spot_price_cop, :demand_mwh, :hydrology_pct,
                     :reservoir_level_pct, :thermal_dispatch_pct,
                     :precio_escasez_cop, :gen_hidraulica_gwh, :gen_termica_gwh,
                     :gen_solar_gwh, :gen_eolica_gwh,
                     :agent_sic_code, :ingested_at)
                ON CONFLICT (timestamp, agent_sic_code)
                DO UPDATE SET
                    spot_price_cop       = EXCLUDED.spot_price_cop,
                    demand_mwh           = EXCLUDED.demand_mwh,
                    hydrology_pct        = EXCLUDED.hydrology_pct,
                    reservoir_level_pct  = EXCLUDED.reservoir_level_pct,
                    thermal_dispatch_pct = EXCLUDED.thermal_dispatch_pct,
                    precio_escasez_cop   = COALESCE(EXCLUDED.precio_escasez_cop, market_data.precio_escasez_cop),
                    gen_hidraulica_gwh   = COALESCE(EXCLUDED.gen_hidraulica_gwh, market_data.gen_hidraulica_gwh),
                    gen_termica_gwh      = COALESCE(EXCLUDED.gen_termica_gwh, market_data.gen_termica_gwh),
                    gen_solar_gwh        = COALESCE(EXCLUDED.gen_solar_gwh, market_data.gen_solar_gwh),
                    gen_eolica_gwh       = COALESCE(EXCLUDED.gen_eolica_gwh, market_data.gen_eolica_gwh),
                    ingested_at          = EXCLUDED.ingested_at
            """)
            conn.execute(stmt, rows)

        logger.info("Upsert completado: %d registros", len(rows))
        return {"records_inserted": len(rows), "date_range": [str(min(prices)), str(max(prices))]}

    @task(task_id="store_raw_to_minio")
    def store_raw_to_minio(prices: dict, demand: dict, gen_by_type: dict) -> str:
        """Guarda copia del raw data en MinIO como parquet para trazabilidad."""
        import sys, tempfile
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_minio_client

        import pandas as pd
        from datetime import datetime, timezone

        if not prices:
            return ""

        rows = []
        for ts, v in prices.items():
            date_str = str(pd.Timestamp(ts).date())
            gen = gen_by_type.get(date_str, {})
            rows.append({
                "timestamp": ts,
                "spot_price_cop": v,
                "demand_mwh": demand.get(ts),
                "gen_hidraulica_gwh": gen.get("hidraulica"),
                "gen_termica_gwh": gen.get("termica"),
                "gen_solar_gwh": gen.get("solar"),
                "gen_eolica_gwh": gen.get("eolica"),
            })
        df = pd.DataFrame(rows)

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
    escasez_data = fetch_escasez_price()
    gen_type_data = fetch_generation_by_type()

    result = store_to_db(
        prices=prices_data,
        demand=demand_data,
        hydrology=hydro_data,
        reservoir=reservoir_data,
        thermal=thermal_data,
        escasez=escasez_data,
        gen_by_type=gen_type_data,
    )

    store_raw_to_minio(prices=prices_data, demand=demand_data, gen_by_type=gen_type_data)


xm_ingestion_dag()
