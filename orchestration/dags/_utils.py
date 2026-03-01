"""
Utilidades compartidas por todos los DAGs de Airflow.
Conexiones a PostgreSQL, MinIO y XM API via variables de entorno.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def get_db_engine():
    """Motor SQLAlchemy síncrono para DAGs de Airflow."""
    from sqlalchemy import create_engine

    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url, pool_pre_ping=True)


def get_minio_client():
    """Cliente MinIO síncrono."""
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )


def get_model_registry():
    """ModelRegistry para guardar/cargar artefactos ML."""
    import sys
    from pathlib import Path

    sys.path.insert(0, "/opt/airflow/ml")
    from registry.model_registry import ModelRegistry

    return ModelRegistry(
        minio_endpoint=os.environ["MINIO_ENDPOINT"],
        minio_user=os.environ["MINIO_ROOT_USER"],
        minio_password=os.environ["MINIO_ROOT_PASSWORD"],
    )


def fetch_date_range(lookback_days: int = 2) -> tuple[date, date]:
    """
    Rango de fechas para ingestion: hoy - lookback_days hasta hoy.
    Siempre re-descargamos los últimos días para garantizar completitud.
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)
    return start, end


def xm_df_to_hourly(df, value_col: str, date_col: str = "Date", hour_col: str = "Hour") -> dict:
    """
    Convierte un DataFrame de pydataxm (Date + Hour + Values)
    a dict {pd.Timestamp: valor} para el merge.
    pydataxm retorna horas como enteros 1–24 → convertir a 0-23.
    """
    import pandas as pd

    result = {}
    for _, row in df.iterrows():
        try:
            hour = int(row[hour_col]) - 1
            ts = pd.Timestamp(str(row[date_col])).replace(hour=hour)
            result[ts] = float(row[value_col])
        except (ValueError, KeyError, TypeError):
            continue
    return result


def xm_df_to_daily(df, value_col: str, date_col: str = "Date") -> dict:
    """
    Convierte DataFrame diario (sin hora) a dict {date: valor}.
    Se replica para todas las horas del día en el merge.
    """
    import pandas as pd

    result = {}
    for _, row in df.iterrows():
        try:
            d = pd.Timestamp(str(row[date_col])).date()
            result[d] = float(row[value_col])
        except (ValueError, KeyError, TypeError):
            continue
    return result
