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


def get_mlflow_client():
    """MLflow tracking client configurado con MinIO como artifact store."""
    import mlflow
    from mlflow.tracking import MlflowClient

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)

    # Configurar credenciales S3/MinIO para artefactos
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL",
                          f"http://{os.environ.get('MINIO_ENDPOINT', 'minio:9000')}")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", os.environ.get("MINIO_ROOT_USER", ""))
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.environ.get("MINIO_ROOT_PASSWORD", ""))

    return MlflowClient(tracking_uri=tracking_uri)


def get_or_create_mlflow_experiment(name: str) -> str:
    """Retorna el experiment_id, creándolo si no existe."""
    import mlflow

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)

    experiment = mlflow.get_experiment_by_name(name)
    if experiment:
        return experiment.experiment_id
    return mlflow.create_experiment(
        name,
        artifact_location="s3://mlflow/",
    )


def fetch_date_range(lookback_days: int = 2, end_offset_days: int = 2) -> tuple[date, date]:
    """
    Rango de fechas para ingestion.
    XM publica datos con ~2 días de lag, por eso el end date es
    hoy - end_offset_days (default=2) en lugar de hoy.
    """
    end = date.today() - timedelta(days=end_offset_days)
    start = end - timedelta(days=lookback_days)
    return start, end


def xm_df_to_hourly(df, value_col: str = None, date_col: str = "Date", hour_col: str = "Hour") -> dict:
    """
    Convierte DataFrame de pydataxm a dict {pd.Timestamp: valor}.
    Soporta formato wide (Values_Hour01..Values_Hour24, pydataxm>=0.3)
    y formato tall (Date + Hour + valor, versiones antiguas).
    """
    import pandas as pd

    result = {}
    hour_cols = sorted([c for c in df.columns if c.startswith("Values_Hour")])

    if hour_cols:
        # Formato wide: una fila por fecha, columna por hora
        for _, row in df.iterrows():
            try:
                d = pd.Timestamp(str(row[date_col]))
            except (ValueError, KeyError):
                continue
            for hcol in hour_cols:
                try:
                    hour_num = int(hcol.replace("Values_Hour", "")) - 1
                    ts = d.replace(hour=hour_num, minute=0, second=0, microsecond=0)
                    result[ts] = float(row[hcol])
                except (ValueError, TypeError):
                    continue
        return result

    # Formato tall (versiones anteriores de pydataxm)
    for _, row in df.iterrows():
        try:
            hour = int(row[hour_col]) - 1
            ts = pd.Timestamp(str(row[date_col])).replace(hour=hour)
            result[ts] = float(row[value_col])
        except (ValueError, KeyError, TypeError):
            continue
    return result


def xm_df_to_daily(df, value_col: str = None, date_col: str = "Date") -> dict:
    """
    Convierte DataFrame diario (sin hora) a dict {date: valor}.
    Detecta automáticamente la columna de valor si no se especifica.
    """
    import pandas as pd

    if value_col is None:
        # La columna numérica que no sea Id ni Date
        candidates = [c for c in df.columns if c not in (date_col, "Id", "Values_code")]
        value_col = candidates[0] if candidates else "Value"

    result = {}
    for _, row in df.iterrows():
        try:
            d = pd.Timestamp(str(row[date_col])).date()
            result[d] = float(row[value_col])
        except (ValueError, KeyError, TypeError):
            continue
    return result
