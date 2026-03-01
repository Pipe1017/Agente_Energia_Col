"""
DAG: model_training
Schedule: diario a las 02:00 (Bogotá)

Entrena un nuevo modelo XGBoost challenger con los últimos 90 días
de features y lo registra en MinIO + PostgreSQL.

Flujo:
  1. load_training_data  → carga features_cache de los últimos 90 días
  2. train_xgboost       → entrena challenger con train/val temporal
  3. evaluate_model      → calcula RMSE, MAE, MAPE, R², coverage
  4. save_to_registry    → guarda artefactos en MinIO + metadata en PG
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "ml-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

TRAIN_LOOKBACK_DAYS = 90
VAL_DAYS = 7


@dag(
    dag_id="model_training",
    schedule="0 2 * * *",   # diario 02:00 Bogotá
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["ml", "training", "xgboost"],
    doc_md=__doc__,
)
def model_training_dag():

    @task(task_id="load_training_data")
    def load_training_data() -> dict:
        """
        Carga features_cache de los últimos TRAIN_LOOKBACK_DAYS días.
        Retorna el DataFrame serializado para XCom.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=TRAIN_LOOKBACK_DAYS)
        logger.info("Cargando features %s → %s", start, end)

        import pandas as pd, json
        from sqlalchemy import text

        engine = get_db_engine()
        query = text("""
            SELECT timestamp, features_json, target_price
            FROM features_cache
            WHERE timestamp >= :start AND timestamp <= :end
              AND target_price IS NOT NULL
            ORDER BY timestamp ASC
        """)

        with engine.connect() as conn:
            rows = conn.execute(query, {"start": str(start), "end": str(end)}).fetchall()

        if not rows:
            raise ValueError(f"Sin datos de features para {start} → {end}")

        records = []
        for row in rows:
            features = json.loads(row.features_json) if isinstance(row.features_json, str) else row.features_json
            record = {"timestamp": str(row.timestamp), "spot_price_cop": row.target_price}
            record.update(features)
            records.append(record)

        logger.info("Registros de entrenamiento: %d", len(records))
        return {"data": records, "start": str(start), "end": str(end)}

    @task(task_id="train_xgboost")
    def train_xgboost(training_payload: dict) -> dict:
        """
        Entrena XGBoostPriceModel (challenger) con split temporal.
        Retorna path temporal del modelo serializado + métricas de validación.
        """
        import sys, tempfile, json
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")

        import numpy as np
        import pandas as pd
        from pathlib import Path
        from features.feature_pipeline import build_feature_matrix, train_val_split, get_X_y
        from models.price_prediction.xgboost_model import XGBoostPriceModel
        from evaluation.metrics import evaluate_all

        data = training_payload["data"]
        if not data:
            raise ValueError("Sin datos para entrenamiento")

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Si ya tiene features calculadas, usarlas directamente
        # Si no, reconstruir con build_feature_matrix
        from features.feature_pipeline import PRICE_PREDICTION_FEATURES
        has_features = all(f in df.columns for f in PRICE_PREDICTION_FEATURES[:5])

        if not has_features:
            logger.info("Reconstruyendo features desde raw market data...")
            feature_df = build_feature_matrix(df, drop_na=True)
        else:
            feature_df = df.copy()

        if len(feature_df) < 200:
            raise ValueError(f"Datos insuficientes para entrenar: {len(feature_df)} filas")

        train_df, val_df = train_val_split(feature_df, val_days=VAL_DAYS)
        X_train, y_train = get_X_y(train_df)
        X_val, y_val = get_X_y(val_df)

        logger.info("Train: %d filas | Val: %d filas", len(X_train), len(X_val))

        model = XGBoostPriceModel()
        model.train(X_train, y_train, X_val=X_val, y_val=y_val)

        # Evaluar en validación
        preds = model.predict(X_val)
        metrics = evaluate_all(y_val.values, preds)
        logger.info("Métricas challenger: %s", metrics)

        # Guardar artefactos en directorio temporal persistente (accesible entre tasks)
        tmpdir = tempfile.mkdtemp(prefix="challenger_")
        model.save(Path(tmpdir))

        return {
            "model_dir": tmpdir,
            "metrics": metrics,
            "train_rows": len(X_train),
            "val_rows": len(X_val),
            "feature_count": X_train.shape[1],
            "trained_on_days": TRAIN_LOOKBACK_DAYS,
        }

    @task(task_id="evaluate_model")
    def evaluate_model(train_result: dict) -> dict:
        """
        Valida métricas mínimas de calidad antes de registrar el modelo.
        Falla el DAG si el modelo no supera umbrales mínimos.
        """
        metrics = train_result["metrics"]
        rmse = metrics.get("rmse", float("inf"))
        mape = metrics.get("mape", float("inf"))

        # Umbrales mínimos de calidad para datos del mercado colombiano
        MAX_RMSE = 100.0   # COP/kWh
        MAX_MAPE = 25.0    # %

        logger.info("Evaluando calidad: RMSE=%.2f (max %s) | MAPE=%.2f%% (max %s%%)",
                    rmse, MAX_RMSE, mape, MAX_MAPE)

        if rmse > MAX_RMSE:
            raise ValueError(f"RMSE demasiado alto: {rmse:.2f} > {MAX_RMSE}")
        if mape > MAX_MAPE:
            raise ValueError(f"MAPE demasiado alto: {mape:.2f}% > {MAX_MAPE}%")

        logger.info("Modelo supera umbrales mínimos de calidad")
        return {**train_result, "quality_check": "passed"}

    @task(task_id="save_to_registry")
    def save_to_registry(eval_result: dict) -> dict:
        """
        Guarda el modelo challenger en MinIO y registra metadata en PostgreSQL.
        El modelo queda en stage='dev' hasta que model_promotion_dag lo promueva.
        """
        import sys, json, uuid
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine, get_model_registry
        from datetime import datetime, timezone
        from pathlib import Path

        model_dir = eval_result["model_dir"]
        metrics = eval_result["metrics"]
        trained_on_days = eval_result["trained_on_days"]

        # Cargar clase del modelo
        sys.path.insert(0, "/opt/airflow/ml")
        from models.price_prediction.xgboost_model import XGBoostPriceModel

        model = XGBoostPriceModel.load(Path(model_dir))

        registry = get_model_registry()
        artifact_path = registry.save_model(
            model=model,
            metrics=metrics,
            params={"train_lookback_days": trained_on_days, "val_days": VAL_DAYS},
            trained_on_days=trained_on_days,
        )

        # Registrar en PostgreSQL como 'dev' (challenger)
        version_id = str(uuid.uuid4())
        version_name = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        engine = get_db_engine()

        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO model_versions
                    (id, name, task, algorithm, version, stage,
                     artifact_path, metrics, params,
                     trained_on_days, trained_at, is_champion)
                VALUES
                    (:id, :name, :task, :algo, :version, 'dev',
                     :artifact_path, :metrics::jsonb, :params::jsonb,
                     :trained_on_days, :trained_at, false)
            """), {
                "id": version_id,
                "name": "xgboost",
                "task": "price_prediction_24h",
                "algo": "XGBoostPriceModel",
                "version": version_name,
                "artifact_path": artifact_path,
                "metrics": json.dumps(metrics),
                "params": json.dumps({"train_lookback_days": trained_on_days, "val_days": VAL_DAYS}),
                "trained_on_days": trained_on_days,
                "trained_at": datetime.now(timezone.utc),
            })

        logger.info("Challenger registrado: id=%s | version=%s | rmse=%.2f",
                    version_id, version_name, metrics.get("rmse", 0))

        # Limpiar directorio temporal
        import shutil
        shutil.rmtree(model_dir, ignore_errors=True)

        return {
            "version_id": version_id,
            "version_name": version_name,
            "artifact_path": artifact_path,
            "metrics": metrics,
        }

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    training_data = load_training_data()
    train_result = train_xgboost(training_data)
    eval_result = evaluate_model(train_result)
    save_to_registry(eval_result)


model_training_dag()
