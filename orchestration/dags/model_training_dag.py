"""
DAG: model_training
Schedule: semanal lunes a las 02:00 (Bogotá)

Entrena un nuevo modelo XGBoost challenger con hasta 6 años de historial
usando pesos por decaimiento exponencial (half-life=365 días):
  - Datos recientes tienen mayor influencia sin olvidar estacionalidad
  - El Niño/La Niña (ciclos 2-4 años) quedan representados
  - Semestres hidrológicos capturados con sin_doy/cos_doy

Flujo:
  1. check_data       → valida que features_cache tiene suficientes datos,
                        retorna solo metadatos (evita XCom de cientos de MB)
  2. train_xgboost    → carga features_cache directo desde BD,
                        calcula pesos temporales, entrena challenger
  3. evaluate_model   → calidad mínima: RMSE, MAPE con umbrales ajustados
  4. save_to_registry → guarda en MLflow (MinIO + PG) como Staging
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

TRAIN_LOOKBACK_DAYS = 6 * 365   # 6 años de historial
VAL_DAYS = 30                   # 30 días validación (vs 7 con 90 días)
WEIGHT_HALF_LIFE_DAYS = 365     # datos de hace 1 año → 50% del peso


@dag(
    dag_id="model_training",
    schedule="0 2 * * 1",   # semanal lunes 02:00 Bogotá
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["ml", "training", "xgboost"],
    doc_md=__doc__,
)
def model_training_dag():

    @task(task_id="check_data")
    def check_data() -> dict:
        """
        Valida que features_cache tiene suficientes datos para entrenar.
        Retorna solo metadatos (count, rango de fechas) — NO los datos brutos.
        Esto evita serializar cientos de MB por XCom.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from datetime import date, timedelta
        from sqlalchemy import text

        end = date.today()
        start = end - timedelta(days=TRAIN_LOOKBACK_DAYS)

        engine = get_db_engine()
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    COUNT(*)                    AS total,
                    MIN(timestamp)              AS min_ts,
                    MAX(timestamp)              AS max_ts,
                    COUNT(DISTINCT DATE(timestamp)) AS days_with_data
                FROM features_cache
                WHERE timestamp >= :start
                  AND timestamp <= :end
                  AND target_price IS NOT NULL
            """), {"start": str(start), "end": str(end)}).fetchone()

        total = row.total or 0
        days = row.days_with_data or 0

        logger.info(
            "features_cache: %d filas | %d días con datos | rango %s → %s",
            total, days, row.min_ts, row.max_ts,
        )

        # Mínimo: 30 días de datos (720 filas) para poder entrenar con lags 168h
        MIN_ROWS = 720
        if total < MIN_ROWS:
            raise ValueError(
                f"Datos insuficientes en features_cache: {total} filas "
                f"(mínimo {MIN_ROWS}). Ejecutar xm_ingestion + feature_engineering primero."
            )

        return {
            "total_rows": int(total),
            "days_with_data": int(days),
            "start": str(start),
            "end": str(end),
            "min_ts": str(row.min_ts),
            "max_ts": str(row.max_ts),
        }

    @task(task_id="train_xgboost")
    def train_xgboost(data_meta: dict) -> dict:
        """
        Carga features_cache directamente desde PostgreSQL (sin pasar por XCom),
        aplica pesos por decaimiento exponencial y entrena XGBoostPriceModel.
        """
        import sys, tempfile, json
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")

        import numpy as np
        import pandas as pd
        from pathlib import Path
        from sqlalchemy import text

        from dags._utils import get_db_engine
        from features.feature_pipeline import (
            PRICE_PREDICTION_FEATURES,
            train_val_split,
            get_X_y,
            compute_sample_weights,
        )
        from models.price_prediction.xgboost_model import XGBoostPriceModel
        from evaluation.metrics import evaluate_all

        start = data_meta["start"]
        end = data_meta["end"]

        logger.info("Cargando features_cache %s → %s ...", start, end)
        engine = get_db_engine()

        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT timestamp, features_json, target_price
                FROM features_cache
                WHERE timestamp >= :start
                  AND timestamp <= :end
                  AND target_price IS NOT NULL
                ORDER BY timestamp ASC
            """), {"start": start, "end": end}).fetchall()

        if not rows:
            raise ValueError(f"Sin features en features_cache para {start} → {end}")

        # Construir DataFrame desde features_cache
        records = []
        for row in rows:
            features = (
                json.loads(row.features_json)
                if isinstance(row.features_json, str)
                else row.features_json
            )
            record = {
                "timestamp": row.timestamp,
                "spot_price_cop": float(row.target_price),
            }
            record.update(features)
            records.append(record)

        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        logger.info("DataFrame cargado: %d filas × %d columnas", *df.shape)

        # Verificar que las features del schema están disponibles
        available = set(df.columns)
        missing_required = [
            f for f in PRICE_PREDICTION_FEATURES
            if f not in available
            and f not in {
                # Opcionales de largo plazo — se imputan con 0 si no están
                "hydrology_rolling_mean_30d", "hydrology_rolling_mean_90d",
                "hydrology_trend_30d", "price_percentile_30d", "price_percentile_365d",
                "ratio_termico_hidro", "ratio_termico_hidro_lag_24h",
                "ratio_termico_hidro_rolling_7d",
                "precio_escasez_cop_ff", "precio_escasez_spread",
                "reservoir_lag_24h", "reservoir_rolling_mean_7d",
            }
        ]
        if missing_required:
            logger.warning(
                "Features requeridas no presentes en features_cache: %s — "
                "los datos son de antes de la actualización del schema. "
                "Se imputarán con 0.",
                missing_required,
            )

        # Imputar features faltantes con 0 (compatibilidad con datos históricos
        # generados antes de agregar las nuevas features estacionales)
        for feat in PRICE_PREDICTION_FEATURES:
            if feat not in df.columns:
                df[feat] = 0.0

        # Split temporal: los últimos VAL_DAYS van a validación
        train_df, val_df = train_val_split(df, val_days=VAL_DAYS)

        if len(train_df) < 168:
            raise ValueError(
                f"Train set demasiado pequeño: {len(train_df)} filas "
                f"(se esperan ≥168 para lags de 1 semana)"
            )

        X_train, y_train = get_X_y(train_df)
        X_val, y_val = get_X_y(val_df)

        # --- Pesos por decaimiento exponencial ---
        # IMPORTANTE: get_X_y descarta el último registro (shift(-1) del target),
        # por eso usamos X_train.index para alinear los timestamps con los pesos.
        train_timestamps = train_df.loc[X_train.index, "timestamp"]
        sample_weight = compute_sample_weights(
            train_timestamps,
            half_life_days=WEIGHT_HALF_LIFE_DAYS,
        )
        logger.info(
            "Train: %d filas | Val: %d filas | pesos: min=%.3f max=%.3f",
            len(X_train), len(X_val),
            float(sample_weight.min()), float(sample_weight.max()),
        )

        model = XGBoostPriceModel()
        model.train(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            sample_weight=sample_weight,
        )

        # Evaluar en validación (sin pesos — métricas de rendimiento puro)
        preds = model.predict(X_val)
        metrics = evaluate_all(y_val.values, preds)
        logger.info("Métricas challenger en validación: %s", metrics)

        # Guardar artefactos en directorio temporal persistente
        tmpdir = tempfile.mkdtemp(prefix="challenger_")
        model.save(Path(tmpdir))

        return {
            "model_dir": tmpdir,
            "metrics": metrics,
            "train_rows": len(X_train),
            "val_rows": len(X_val),
            "feature_count": X_train.shape[1],
            "trained_on_days": data_meta["days_with_data"],
            "weight_half_life_days": WEIGHT_HALF_LIFE_DAYS,
            "data_start": data_meta["min_ts"],
            "data_end": data_meta["max_ts"],
        }

    @task(task_id="evaluate_model")
    def evaluate_model(train_result: dict) -> dict:
        """
        Valida métricas mínimas de calidad antes de registrar el modelo.
        Falla el DAG si el modelo no supera umbrales mínimos.
        Umbrales calibrados para el mercado colombiano con historial de largo plazo.
        """
        metrics = train_result["metrics"]
        rmse = metrics.get("rmse", float("inf"))
        mape = metrics.get("mape", float("inf"))

        # Umbrales para modelo entrenado en 6 años de datos colombianos
        # RMSE de 120 permite capturar picos de crisis sin penalizar excesivo
        MAX_RMSE = 120.0   # COP/kWh — más flexible que 90 días
        MAX_MAPE = 30.0    # % — precios extremos dificultan el MAPE

        logger.info(
            "Calidad: RMSE=%.2f (max %.0f) | MAPE=%.2f%% (max %.0f%%) | "
            "Datos: %d días de historia",
            rmse, MAX_RMSE, mape, MAX_MAPE,
            train_result.get("trained_on_days", 0),
        )

        if rmse > MAX_RMSE:
            raise ValueError(f"RMSE demasiado alto: {rmse:.2f} > {MAX_RMSE}")
        if mape > MAX_MAPE:
            raise ValueError(f"MAPE demasiado alto: {mape:.2f}% > {MAX_MAPE}%")

        logger.info("Modelo supera umbrales mínimos de calidad ✓")
        return {**train_result, "quality_check": "passed"}

    @task(task_id="save_to_registry")
    def save_to_registry(eval_result: dict) -> dict:
        """
        Registra el modelo challenger en MLflow (tracking + Model Registry).
        MLflow usa MinIO como artifact store (S3-compatible).
        El modelo queda en stage 'Staging' hasta que model_promotion_dag lo promueva.
        """
        import sys, os, uuid, shutil
        sys.path.insert(0, "/opt/airflow")
        sys.path.insert(0, "/opt/airflow/ml")

        from dags._utils import get_or_create_mlflow_experiment
        from pathlib import Path

        import mlflow
        import mlflow.xgboost
        from mlflow.tracking import MlflowClient

        model_dir = eval_result["model_dir"]
        metrics = eval_result["metrics"]
        trained_on_days = eval_result.get("trained_on_days", 0)
        train_rows = eval_result.get("train_rows", 0)
        weight_half_life = eval_result.get("weight_half_life_days", WEIGHT_HALF_LIFE_DAYS)

        MODEL_NAME = "xgboost_price_predictor"
        EXPERIMENT = "price_prediction_24h"
        TASK = "price_prediction_24h"

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        os.environ.setdefault(
            "MLFLOW_S3_ENDPOINT_URL",
            f"http://{os.environ.get('MINIO_ENDPOINT', 'minio:9000')}",
        )
        os.environ.setdefault("AWS_ACCESS_KEY_ID", os.environ.get("MINIO_ROOT_USER", ""))
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.environ.get("MINIO_ROOT_PASSWORD", ""))

        mlflow.set_tracking_uri(tracking_uri)
        experiment_id = get_or_create_mlflow_experiment(EXPERIMENT)
        domain_id = str(uuid.uuid4())

        from models.price_prediction.xgboost_model import XGBoostPriceModel
        model = XGBoostPriceModel.load(Path(model_dir))

        with mlflow.start_run(experiment_id=experiment_id) as run:
            mlflow.log_params({
                "train_lookback_days": TRAIN_LOOKBACK_DAYS,
                "val_days": VAL_DAYS,
                "train_rows": train_rows,
                "trained_on_days": trained_on_days,
                "weight_half_life_days": weight_half_life,
                "algorithm": "XGBoostPriceModel",
                "task": TASK,
            })
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})

            # Loguear modelo cuantil median (q=0.5) como artefacto MLflow principal
            mlflow.xgboost.log_model(
                model._model_mid,          # ← correcto: _model_mid, no _models[0.5]
                artifact_path="model",
                registered_model_name=MODEL_NAME,
            )

            # Guardar el paquete completo (3 cuantiles) como artefacto raw
            mlflow.log_artifacts(model_dir, artifact_path="full_model")

            run_id = run.info.run_id
            artifact_uri = f"runs:/{run_id}/full_model"

        # Mover a Staging para que model_promotion_dag evalúe
        client = MlflowClient(tracking_uri=tracking_uri)
        latest = client.get_latest_versions(MODEL_NAME, ["None"])
        registered_version = latest[0].version if latest else "1"

        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=registered_version,
            stage="Staging",
        )

        for key, val in {
            "domain_id": domain_id,
            "task": TASK,
            "trained_on_days": str(trained_on_days),
            "weight_half_life_days": str(weight_half_life),
            "data_start": eval_result.get("data_start", ""),
            "data_end": eval_result.get("data_end", ""),
            **{f"metric.{k}": str(v) for k, v in metrics.items()},
        }.items():
            client.set_model_version_tag(MODEL_NAME, registered_version, key, val)

        logger.info(
            "Challenger registrado: %s@%s | run_id=%s | rmse=%.2f | "
            "%d días de historia | half_life=%d días",
            MODEL_NAME, registered_version, run_id,
            metrics.get("rmse", 0), trained_on_days, weight_half_life,
        )

        shutil.rmtree(model_dir, ignore_errors=True)

        return {
            "version_id": domain_id,
            "version_name": registered_version,
            "artifact_path": artifact_uri,
            "mlflow_run_id": run_id,
            "metrics": metrics,
        }

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    data_meta = check_data()
    train_result = train_xgboost(data_meta)
    eval_result = evaluate_model(train_result)
    save_to_registry(eval_result)


model_training_dag()
