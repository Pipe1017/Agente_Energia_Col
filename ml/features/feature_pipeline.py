"""
Pipeline completo de feature engineering para el modelo de precio.

Input:  DataFrame con datos crudos de XM (market_data de PostgreSQL)
Output: DataFrame listo para entrenamiento o predicción

El pipeline es reproducible y determinista dado el mismo input.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .calendar_features import add_calendar_features
from .lag_features import add_lag_features

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Schema canónico de features para price_prediction_24h
# Este es el contrato entre el pipeline y XGBoostPriceModel
# ------------------------------------------------------------------
PRICE_PREDICTION_FEATURES: list[str] = [
    # Temporales cíclicos
    "sin_hour", "cos_hour",
    "sin_dow", "cos_dow",
    # Temporales categóricos
    "hour_of_day", "day_of_week", "month", "week_of_year",
    # Indicadores de día
    "is_holiday", "is_weekend", "is_working_day", "is_pre_holiday",
    "is_peak_hour", "is_off_peak",
    # Mercado (valores actuales)
    "demand_mwh", "hydrology_pct", "reservoir_level_pct", "thermal_dispatch_pct",
    # Lags de precio
    "spot_price_lag_1h", "spot_price_lag_2h", "spot_price_lag_3h",
    "spot_price_lag_24h", "spot_price_lag_48h", "spot_price_lag_168h",
    # Rolling stats de precio
    "spot_price_rolling_mean_6h", "spot_price_rolling_mean_24h",
    "spot_price_rolling_mean_168h", "spot_price_rolling_std_24h",
    "spot_price_rolling_max_24h", "spot_price_rolling_min_24h",
    # Diferencias (velocidad de cambio del precio)
    "spot_price_diff_1h", "spot_price_diff_24h",
    # Lags de demanda
    "demand_lag_1h", "demand_lag_24h", "demand_rolling_mean_24h",
    # Hidrología rolling
    "hydrology_rolling_mean_7d", "hydrology_trend_7d",
]


def build_feature_matrix(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    drop_na: bool = True,
) -> pd.DataFrame:
    """
    Construye la matriz de features completa desde datos crudos de mercado.

    Args:
        df: DataFrame con columnas mínimas:
            timestamp, spot_price_cop, demand_mwh, hydrology_pct,
            reservoir_level_pct, thermal_dispatch_pct
        timestamp_col: nombre de la columna de tiempo
        drop_na: si True, elimina filas con NaN (necesario para entrenar)

    Returns:
        DataFrame con exactamente las columnas de PRICE_PREDICTION_FEATURES
        más las columnas originales de mercado y spot_price_cop como target.
    """
    required_cols = {
        "spot_price_cop", "demand_mwh", "hydrology_pct",
        "reservoir_level_pct", "thermal_dispatch_pct",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en el DataFrame: {missing}")

    logger.info("Construyendo features para %d registros...", len(df))

    # 1. Ordenar por timestamp
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    # 2. Features de calendario
    df = add_calendar_features(df, timestamp_col=timestamp_col)

    # 3. Lags y rolling stats
    df = add_lag_features(
        df,
        price_col="spot_price_cop",
        demand_col="demand_mwh",
        hydrology_col="hydrology_pct",
        sort_col=timestamp_col,
    )

    # 4. Eliminar filas sin features completas (primeras N horas)
    if drop_na:
        n_before = len(df)
        df = df.dropna(subset=PRICE_PREDICTION_FEATURES)
        n_dropped = n_before - len(df)
        if n_dropped > 0:
            logger.info("Eliminadas %d filas con NaN en features (lags iniciales)", n_dropped)

    logger.info("Feature matrix: %d filas × %d features", len(df), len(PRICE_PREDICTION_FEATURES))
    return df


def get_X_y(
    df: pd.DataFrame,
    target_col: str = "spot_price_cop",
    horizon_hours: int = 1,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Extrae X (features) e y (target) del DataFrame con features construidas.

    horizon_hours: horas hacia adelante a predecir.
        1 = predecir precio en t+1 usando features en t
        24 = predecir precio en t+24 usando features en t
    """
    df = df.copy()
    df["target"] = df[target_col].shift(-horizon_hours)
    df = df.dropna(subset=["target"])

    X = df[PRICE_PREDICTION_FEATURES]
    y = df["target"]

    return X, y


def train_val_split(
    df: pd.DataFrame,
    val_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    División temporal: los últimos `val_days` días van a validación.
    Nunca mezclar temporal → no usar train_test_split aleatorio.
    """
    cutoff = df["timestamp"].max() - pd.Timedelta(days=val_days)
    train = df[df["timestamp"] <= cutoff].copy()
    val = df[df["timestamp"] > cutoff].copy()
    logger.info(
        "Split: train=%d rows (hasta %s), val=%d rows (desde %s)",
        len(train), cutoff.date(), len(val), (cutoff + pd.Timedelta(hours=1)).date(),
    )
    return train, val
