"""
DAG: model_promotion
Schedule: diario a las 03:00 (Bogotá), después de model_training

Implementa el patrón Champion/Challenger:
  1. Obtiene el champion actual (stage='production') desde PostgreSQL
  2. Obtiene el último challenger (stage='dev') entrenado hoy
  3. Compara métricas usando champion_challenger.py
  4. Si challenger mejora ≥ 2% en RMSE → promueve a production
  5. Archiva el ex-champion y todos los challengers restantes

El DAG envía el resultado al log (sin notificación externa en esta versión).
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
    "retry_delay": timedelta(minutes=10),
}

MIN_IMPROVEMENT_PCT = 2.0   # % mínimo de mejora en RMSE para promover


@dag(
    dag_id="model_promotion",
    schedule="0 3 * * *",   # diario 03:00 Bogotá
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["ml", "promotion", "champion-challenger"],
    doc_md=__doc__,
)
def model_promotion_dag():

    @task(task_id="get_champion")
    def get_champion() -> dict:
        """
        Obtiene el modelo champion actual (MLflow stage='Production').
        Retorna {} si no existe champion (primera vez).
        """
        import sys, os
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_mlflow_client

        MODEL_NAME = "xgboost_price_predictor"
        client = get_mlflow_client()

        try:
            versions = client.get_latest_versions(MODEL_NAME, ["Production"])
        except Exception:
            logger.info("No existe champion actual — primer entrenamiento")
            return {}

        if not versions:
            logger.info("No existe champion actual — primer entrenamiento")
            return {}

        mv = versions[0]
        tags = mv.tags or {}
        metrics = {
            k.removeprefix("metric."): float(v)
            for k, v in tags.items()
            if k.startswith("metric.")
        }

        logger.info("Champion actual: %s@%s | rmse=%.2f",
                    MODEL_NAME, mv.version, metrics.get("rmse", 0))
        return {
            "id": tags.get("domain_id", mv.version),
            "version": mv.version,
            "artifact_path": mv.source or f"models:/{MODEL_NAME}/{mv.version}",
            "metrics": metrics,
            "mlflow_version": mv.version,
        }

    @task(task_id="get_challenger")
    def get_challenger() -> dict:
        """
        Obtiene el challenger más reciente (MLflow stage='Staging').
        Falla si no hay challenger disponible.
        """
        import sys, os
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_mlflow_client

        MODEL_NAME = "xgboost_price_predictor"
        client = get_mlflow_client()

        try:
            versions = client.get_latest_versions(MODEL_NAME, ["Staging"])
        except Exception as exc:
            raise ValueError(f"No hay challenger disponible en MLflow: {exc}") from exc

        if not versions:
            raise ValueError("No hay challenger disponible en MLflow stage=Staging")

        mv = versions[0]
        tags = mv.tags or {}
        metrics = {
            k.removeprefix("metric."): float(v)
            for k, v in tags.items()
            if k.startswith("metric.")
        }

        logger.info("Challenger: %s@%s | rmse=%.2f",
                    MODEL_NAME, mv.version, metrics.get("rmse", 0))
        return {
            "id": tags.get("domain_id", mv.version),
            "version": mv.version,
            "artifact_path": mv.source or f"models:/{MODEL_NAME}/{mv.version}",
            "metrics": metrics,
            "trained_on_days": int(tags.get("trained_on_days", 90)),
            "mlflow_version": mv.version,
        }

    @task(task_id="compare_and_decide")
    def compare_and_decide(champion: dict, challenger: dict) -> dict:
        """
        Compara métricas usando el patrón champion/challenger.
        Retorna la decisión: 'promote' o 'keep_champion'.
        """
        import sys
        sys.path.insert(0, "/opt/airflow/ml")
        from evaluation.champion_challenger import should_promote, full_comparison_report

        if not champion:
            # Sin champion → promover automáticamente el primer modelo
            logger.info("Sin champion previo — promoviendo challenger automáticamente")
            return {
                "decision": "promote",
                "reason": "Primer modelo — promoción automática",
                "champion": champion,
                "challenger": challenger,
            }

        promote, reason = should_promote(
            champion_metrics=champion["metrics"],
            challenger_metrics=challenger["metrics"],
            primary_metric="rmse",
            min_improvement_pct=MIN_IMPROVEMENT_PCT,
        )

        report = full_comparison_report(champion["metrics"], challenger["metrics"])
        decision = "promote" if promote else "keep_champion"

        logger.info("Decisión: %s | Razón: %s", decision, reason)
        for metric, comparison in report.get("comparison", {}).items():
            logger.info("  %s: champion=%.3f | challenger=%.3f | mejora=%.1f%%",
                        metric, comparison.get("champion", 0),
                        comparison.get("challenger", 0),
                        comparison.get("improvement_pct", 0))

        return {
            "decision": decision,
            "reason": reason,
            "report": report,
            "champion": champion,
            "challenger": challenger,
        }

    @task(task_id="execute_promotion")
    def execute_promotion(comparison_result: dict) -> dict:
        """
        Ejecuta la promoción en MLflow usando stage transitions:
          - 'promote'       → challenger: Staging → Production, champion: Production → Archived
          - 'keep_champion' → challenger: Staging → Archived (evaluado, rechazado)
        """
        import sys, os
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_mlflow_client

        MODEL_NAME = "xgboost_price_predictor"
        decision = comparison_result["decision"]
        champion = comparison_result["champion"]
        challenger = comparison_result["challenger"]
        client = get_mlflow_client()

        if decision != "promote":
            logger.info("Manteniendo champion — archivando challenger evaluado")
            client.transition_model_version_stage(
                name=MODEL_NAME,
                version=challenger["mlflow_version"],
                stage="Archived",
            )
            client.set_model_version_tag(
                MODEL_NAME, challenger["mlflow_version"],
                "promotion_result", "rejected",
            )
            return {"action": "kept_champion", "challenger_stage": "Archived"}

        # 1. Archivar champion actual
        if champion.get("mlflow_version"):
            client.transition_model_version_stage(
                name=MODEL_NAME,
                version=champion["mlflow_version"],
                stage="Archived",
            )
            logger.info("Champion archivado: %s@%s", MODEL_NAME, champion["mlflow_version"])

        # 2. Promover challenger a Production
        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=challenger["mlflow_version"],
            stage="Production",
        )
        client.set_model_version_tag(
            MODEL_NAME, challenger["mlflow_version"],
            "promoted_by", "airflow_dag",
        )
        client.set_model_version_tag(
            MODEL_NAME, challenger["mlflow_version"],
            "promotion_result", "promoted",
        )
        logger.info("Challenger promovido a Production: %s@%s",
                    MODEL_NAME, challenger["mlflow_version"])

        return {
            "action": "promoted",
            "new_champion_id": challenger["id"],
            "new_champion_version": challenger["mlflow_version"],
            "reason": comparison_result["reason"],
        }

    @task(task_id="log_promotion_result")
    def log_promotion_result(promotion_result: dict, comparison_result: dict) -> None:
        """Log estructurado del resultado de la promoción para auditoría."""
        import json
        summary = {
            "action": promotion_result.get("action"),
            "reason": comparison_result.get("reason"),
            "new_champion": promotion_result.get("new_champion_version"),
            "metrics_comparison": comparison_result.get("report", {}).get("comparison", {}),
        }
        logger.info("=== PROMOTION RESULT ===\n%s", json.dumps(summary, indent=2))

    # ------------------------------------------------------------------
    # Grafo de dependencias
    # ------------------------------------------------------------------
    champion_data = get_champion()
    challenger_data = get_challenger()
    comparison = compare_and_decide(champion_data, challenger_data)
    promotion = execute_promotion(comparison)
    log_promotion_result(promotion, comparison)


model_promotion_dag()
