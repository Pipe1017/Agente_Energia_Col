"""
Pipeline completo de feature engineering para el modelo de precio.

Input:  DataFrame con datos crudos de XM (market_data de PostgreSQL)
Output: DataFrame listo para entrenamiento o predicción

El pipeline es reproducible y determinista dado el mismo input.
Para entrenamiento con historial de 6 años, usar compute_sample_weights()
para ponderar datos recientes sin olvidar estacionalidad histórica.
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
    # Temporales cíclicos — ciclo diario y semanal
    "sin_hour", "cos_hour",
    "sin_dow", "cos_dow",
    # Ciclo anual cíclico (El Niño/La Niña, temporadas hidrológicas)
    "sin_doy", "cos_doy",
    # Semestre hidrológico colombiano (1=húmedo abr-nov, 0=seco dic-mar)
    "semestre_hidrologico",
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
    # Rolling stats de precio (corto plazo)
    "spot_price_rolling_mean_6h", "spot_price_rolling_mean_24h",
    "spot_price_rolling_mean_168h", "spot_price_rolling_std_24h",
    "spot_price_rolling_max_24h", "spot_price_rolling_min_24h",
    # Diferencias (velocidad de cambio del precio)
    "spot_price_diff_1h", "spot_price_diff_24h",
    # Lags de demanda
    "demand_lag_1h", "demand_lag_24h", "demand_rolling_mean_24h",
    # Hidrología rolling — corto plazo
    "hydrology_rolling_mean_7d", "hydrology_trend_7d",
    # Hidrología rolling — largo plazo (señal de sequía / El Niño)
    "hydrology_rolling_mean_30d", "hydrology_rolling_mean_90d",
    "hydrology_trend_30d",
    # Embalse rolling (complementa hidrología)
    "reservoir_lag_24h", "reservoir_rolling_mean_7d",
    # Percentil histórico del precio (contexto de largo plazo)
    "price_percentile_30d", "price_percentile_365d",
    # Ratio térmico/hidráulico (driver principal del precio según SIMEM)
    "ratio_termico_hidro", "ratio_termico_hidro_lag_24h", "ratio_termico_hidro_rolling_7d",
    # Señal regulatoria: spread vs precio de escasez CREG
    "precio_escasez_cop_ff", "precio_escasez_spread",
]

# Features opcionales — si no están disponibles se imputan con 0
# Incluye las de largo plazo que requieren historial extenso
OPTIONAL_FEATURES: set[str] = {
    "ratio_termico_hidro", "ratio_termico_hidro_lag_24h", "ratio_termico_hidro_rolling_7d",
    "precio_escasez_cop_ff", "precio_escasez_spread",
    "reservoir_lag_24h", "reservoir_rolling_mean_7d",
    # Largo plazo: disponibles solo cuando hay suficiente historial
    "hydrology_rolling_mean_30d", "hydrology_rolling_mean_90d", "hydrology_trend_30d",
    "price_percentile_30d", "price_percentile_365d",
}


def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta y limpia datos anómalos del mercado eléctrico colombiano.

    Conserva precios extremos reales (crisis de sequía, eventos regulatorios)
    pero corrige valores físicamente imposibles: precios negativos, demanda cero,
    hidrología fuera de rango, etc.

    Llama esta función ANTES de build_feature_matrix para entrenamiento.
    """
    df = df.copy()
    n_original = len(df)

    # -- Precio spot: nunca negativo ni cero en mercado colombiano --
    mask_bad_price = df["spot_price_cop"] <= 0
    if mask_bad_price.any():
        logger.warning(
            "Precio ≤0 en %d registros → reemplazando con forward-fill",
            mask_bad_price.sum(),
        )
        df.loc[mask_bad_price, "spot_price_cop"] = np.nan
        df["spot_price_cop"] = df["spot_price_cop"].ffill().bfill()

    # Log de precios extremos (los conservamos, son datos de crisis reales)
    crisis = df["spot_price_cop"] > 2000
    if crisis.any():
        logger.info(
            "%d precios > 2000 COP/kWh (posibles crisis de sequía — conservados)",
            crisis.sum(),
        )

    # -- Demanda: cero o negativo = dato faltante --
    if "demand_mwh" in df.columns:
        mask_bad_demand = df["demand_mwh"] <= 0
        if mask_bad_demand.any():
            logger.warning(
                "Demanda ≤0 en %d registros → forward-fill",
                mask_bad_demand.sum(),
            )
            df.loc[mask_bad_demand, "demand_mwh"] = np.nan
            df["demand_mwh"] = df["demand_mwh"].ffill().bfill()

    # -- Hidrología: rango físico 0-300% (puede superar 100% en años muy húmedos) --
    if "hydrology_pct" in df.columns:
        out = (df["hydrology_pct"] < 0) | (df["hydrology_pct"] > 300)
        if out.any():
            logger.warning("Hidrología fuera de [0,300]%% en %d registros → clip", out.sum())
            df["hydrology_pct"] = df["hydrology_pct"].clip(0.0, 300.0)

    # -- Nivel de embalse: 0-100% --
    if "reservoir_level_pct" in df.columns:
        df["reservoir_level_pct"] = df["reservoir_level_pct"].clip(0.0, 100.0)

    # -- Despacho térmico: 0-100% --
    if "thermal_dispatch_pct" in df.columns:
        df["thermal_dispatch_pct"] = df["thermal_dispatch_pct"].clip(0.0, 100.0)

    # -- Precio de escasez: forward-fill gaps (cambia mensualmente por CREG) --
    if "precio_escasez_cop" in df.columns:
        nas = df["precio_escasez_cop"].isna().sum()
        if nas > 0:
            df["precio_escasez_cop"] = df["precio_escasez_cop"].ffill()

    logger.info(
        "Validación completada: %d/%d registros válidos tras limpieza",
        len(df.dropna(subset=["spot_price_cop", "demand_mwh"])),
        n_original,
    )
    return df


def compute_sample_weights(
    timestamps: pd.Series,
    half_life_days: int = 365,
) -> np.ndarray:
    """
    Pesos por decaimiento exponencial para entrenamiento temporal.

    Los datos recientes reciben más peso sin olvidar estacionalidad histórica.
    Con half_life_days=365 (default):
      - Datos de hace 6 meses: peso ≈ 0.71
      - Datos de hace 1 año:   peso ≈ 0.50
      - Datos de hace 3 años:  peso ≈ 0.13
      - Datos de hace 6 años:  peso ≈ 0.02

    Args:
        timestamps: Serie de timestamps del dataset de entrenamiento
        half_life_days: días para que el peso caiga a la mitad (default 365)

    Returns:
        Array float32 con pesos [0, 1] para cada muestra
    """
    ts = pd.to_datetime(timestamps)
    max_ts = ts.max()
    days_ago = (max_ts - ts).dt.total_seconds() / 86400.0
    weights = np.exp(-np.log(2) * days_ago / half_life_days)
    return weights.values.astype(np.float32)


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
        drop_na: si True, elimina filas con NaN en features obligatorias

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

    # 1. Validar y limpiar datos de entrada
    df = validate_and_clean(df)

    # 2. Ordenar por timestamp
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    # 3. Features de calendario
    df = add_calendar_features(df, timestamp_col=timestamp_col)

    # 4. Lags, rolling stats y variables derivadas
    df = add_lag_features(
        df,
        price_col="spot_price_cop",
        demand_col="demand_mwh",
        hydrology_col="hydrology_pct",
        reservoir_col="reservoir_level_pct",
        sort_col=timestamp_col,
    )

    # 5. Imputar features opcionales no disponibles con 0
    for feat in OPTIONAL_FEATURES:
        if feat not in df.columns:
            df[feat] = 0.0
            logger.debug("Feature opcional '%s' imputada con 0", feat)

    # 6. Eliminar filas sin features obligatorias completas (primeras N horas)
    required_features = [f for f in PRICE_PREDICTION_FEATURES if f not in OPTIONAL_FEATURES]
    if drop_na:
        n_before = len(df)
        df = df.dropna(subset=required_features)
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
