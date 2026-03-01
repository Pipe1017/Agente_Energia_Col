"""
Métricas de evaluación para modelos de predicción de precio.

Métricas implementadas:
  - RMSE: Root Mean Squared Error (penaliza errores grandes)
  - MAE:  Mean Absolute Error (robusto a outliers)
  - MAPE: Mean Absolute Percentage Error (interpretable como %)
  - SMAPE: Symmetric MAPE (maneja ceros mejor que MAPE)
  - R2:   Coeficiente de determinación
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rmse(y_true: np.ndarray | pd.Series, y_pred: np.ndarray) -> float:
    """Root Mean Squared Error — en las mismas unidades que el precio (COP/kWh)."""
    return float(np.sqrt(np.mean((np.asarray(y_true) - y_pred) ** 2)))


def mae(y_true: np.ndarray | pd.Series, y_pred: np.ndarray) -> float:
    """Mean Absolute Error — en COP/kWh."""
    return float(np.mean(np.abs(np.asarray(y_true) - y_pred)))


def mape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    """
    Mean Absolute Percentage Error — en porcentaje.
    eps evita división por cero cuando y_true ≈ 0.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    return float(np.mean(np.abs((y_true_arr - y_pred) / (np.abs(y_true_arr) + eps))) * 100)


def smape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray) -> float:
    """Symmetric MAPE — más estable que MAPE cuando y_true puede ser 0."""
    y_true_arr = np.asarray(y_true, dtype=float)
    denom = (np.abs(y_true_arr) + np.abs(y_pred)) / 2 + 1e-6
    return float(np.mean(np.abs(y_true_arr - y_pred) / denom) * 100)


def r2(y_true: np.ndarray | pd.Series, y_pred: np.ndarray) -> float:
    """Coeficiente de determinación R². Rango [-∞, 1]. 1 = perfecto."""
    y_true_arr = np.asarray(y_true, dtype=float)
    ss_res = np.sum((y_true_arr - y_pred) ** 2)
    ss_tot = np.sum((y_true_arr - y_true_arr.mean()) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-10))


def coverage_rate(
    y_true: np.ndarray | pd.Series,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """
    Tasa de cobertura del intervalo de confianza.
    Fracción de valores reales que caen dentro del intervalo predicho.
    Para un IC del 90%, esperamos ~0.90.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    inside = (y_true_arr >= lower) & (y_true_arr <= upper)
    return float(inside.mean())


def evaluate_all(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
) -> dict[str, float]:
    """
    Calcula todas las métricas de una vez.
    Retorna dict listo para guardar en model_versions.metrics (JSONB).
    """
    results = {
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "mape": mape(y_true, y_pred),
        "smape": smape(y_true, y_pred),
        "r2": r2(y_true, y_pred),
    }
    if lower is not None and upper is not None:
        results["coverage_rate_90"] = coverage_rate(y_true, lower, upper)
        results["avg_interval_width"] = float(np.mean(upper - lower))
    return results
