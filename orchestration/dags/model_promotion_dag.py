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
        Obtiene el modelo champion actual (stage='production', is_champion=True).
        Retorna {} si no existe champion (primera vez).
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        import json
        from sqlalchemy import text

        engine = get_db_engine()
        query = text("""
            SELECT id, name, version, artifact_path, metrics, trained_on_days
            FROM model_versions
            WHERE stage = 'production' AND is_champion = true
            ORDER BY trained_at DESC
            LIMIT 1
        """)

        with engine.connect() as conn:
            row = conn.execute(query).fetchone()

        if not row:
            logger.info("No existe champion actual — primer entrenamiento")
            return {}

        metrics = row.metrics if isinstance(row.metrics, dict) else json.loads(row.metrics)
        logger.info("Champion actual: id=%s | version=%s | rmse=%.2f",
                    row.id, row.version, metrics.get("rmse", 0))
        return {
            "id": str(row.id),
            "version": row.version,
            "artifact_path": row.artifact_path,
            "metrics": metrics,
        }

    @task(task_id="get_challenger")
    def get_challenger() -> dict:
        """
        Obtiene el challenger más reciente (stage='dev') para comparar.
        Falla si no hay challenger disponible.
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        import json
        from sqlalchemy import text

        engine = get_db_engine()
        query = text("""
            SELECT id, name, version, artifact_path, metrics, trained_on_days
            FROM model_versions
            WHERE stage = 'dev'
            ORDER BY trained_at DESC
            LIMIT 1
        """)

        with engine.connect() as conn:
            row = conn.execute(query).fetchone()

        if not row:
            raise ValueError("No hay challenger disponible para comparar")

        metrics = row.metrics if isinstance(row.metrics, dict) else json.loads(row.metrics)
        logger.info("Challenger: id=%s | version=%s | rmse=%.2f",
                    row.id, row.version, metrics.get("rmse", 0))
        return {
            "id": str(row.id),
            "version": row.version,
            "artifact_path": row.artifact_path,
            "metrics": metrics,
            "trained_on_days": row.trained_on_days,
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
        Ejecuta la promoción si la decisión es 'promote':
          - champion anterior → stage='archived', is_champion=False
          - challenger → stage='production', is_champion=True
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import get_db_engine
        from sqlalchemy import text
        from datetime import datetime, timezone

        decision = comparison_result["decision"]
        champion = comparison_result["champion"]
        challenger = comparison_result["challenger"]

        if decision != "promote":
            logger.info("Manteniendo champion actual — sin cambios en DB")
            # Marcar challenger como 'staged' (evaluado pero no promovido)
            engine = get_db_engine()
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE model_versions
                    SET stage = 'staging'
                    WHERE id = :id
                """), {"id": challenger["id"]})
            return {"action": "kept_champion", "challenger_stage": "staging"}

        engine = get_db_engine()
        with engine.begin() as conn:
            # 1. Archivar champion actual
            if champion:
                conn.execute(text("""
                    UPDATE model_versions
                    SET stage = 'archived', is_champion = false
                    WHERE id = :id
                """), {"id": champion["id"]})
                logger.info("Champion archivado: id=%s", champion["id"])

            # 2. Archivar todos los demás 'dev' y 'staging' (limpiar)
            conn.execute(text("""
                UPDATE model_versions
                SET stage = 'archived'
                WHERE stage IN ('dev', 'staging') AND id != :challenger_id
            """), {"challenger_id": challenger["id"]})

            # 3. Promover challenger
            conn.execute(text("""
                UPDATE model_versions
                SET stage = 'production',
                    is_champion = true,
                    promoted_at = :promoted_at
                WHERE id = :id
            """), {
                "id": challenger["id"],
                "promoted_at": datetime.now(timezone.utc),
            })
            logger.info("Challenger promovido a production: id=%s | version=%s",
                        challenger["id"], challenger["version"])

        return {
            "action": "promoted",
            "new_champion_id": challenger["id"],
            "new_champion_version": challenger["version"],
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
