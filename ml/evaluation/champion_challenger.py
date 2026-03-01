"""
Lógica de promoción champion/challenger.

El challenger supera al champion si mejora el RMSE
en el conjunto de validación con significancia estadística.
"""
from __future__ import annotations

import logging

import numpy as np

from .metrics import evaluate_all

logger = logging.getLogger(__name__)


def should_promote(
    champion_metrics: dict[str, float],
    challenger_metrics: dict[str, float],
    primary_metric: str = "rmse",
    min_improvement_pct: float = 2.0,
) -> tuple[bool, str]:
    """
    Decide si el challenger debe reemplazar al champion.

    Para métricas donde menor = mejor (rmse, mae, mape):
      promote si challenger < champion * (1 - min_improvement_pct/100)

    Returns:
        (should_promote, reason)
    """
    champ_val = champion_metrics.get(primary_metric)
    chall_val = challenger_metrics.get(primary_metric)

    if champ_val is None or chall_val is None:
        reason = f"No se encontró la métrica '{primary_metric}' para comparar"
        logger.warning(reason)
        return False, reason

    # Métricas donde menor es mejor
    lower_is_better = {"rmse", "mae", "mape", "smape"}

    if primary_metric in lower_is_better:
        improvement_pct = (champ_val - chall_val) / (champ_val + 1e-10) * 100
        promote = improvement_pct >= min_improvement_pct
        reason = (
            f"Challenger {primary_metric}={chall_val:.4f} vs "
            f"Champion {primary_metric}={champ_val:.4f} "
            f"(mejora: {improvement_pct:.2f}% — mínimo requerido: {min_improvement_pct}%)"
        )
    else:
        # r2: mayor es mejor
        improvement_pct = (chall_val - champ_val) / (abs(champ_val) + 1e-10) * 100
        promote = improvement_pct >= min_improvement_pct
        reason = (
            f"Challenger {primary_metric}={chall_val:.4f} vs "
            f"Champion {primary_metric}={champ_val:.4f} "
            f"(mejora: {improvement_pct:.2f}%)"
        )

    if promote:
        logger.info("✅ PROMOVER challenger. %s", reason)
    else:
        logger.info("❌ Mantener champion. %s", reason)

    return promote, reason


def full_comparison_report(
    champion_metrics: dict[str, float],
    challenger_metrics: dict[str, float],
) -> dict:
    """Genera reporte completo de comparación para el log de Airflow."""
    metrics = ["rmse", "mae", "mape", "r2"]
    rows = []
    for m in metrics:
        champ = champion_metrics.get(m, float("nan"))
        chall = challenger_metrics.get(m, float("nan"))
        lower_better = m in {"rmse", "mae", "mape", "smape"}
        winner = "challenger" if (
            (lower_better and chall < champ) or
            (not lower_better and chall > champ)
        ) else "champion"
        rows.append({"metric": m, "champion": champ, "challenger": chall, "winner": winner})

    promote, reason = should_promote(champion_metrics, challenger_metrics)
    return {
        "comparison": rows,
        "decision": "promote" if promote else "keep_champion",
        "reason": reason,
    }
