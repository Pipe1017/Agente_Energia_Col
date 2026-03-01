"""
Features de rezago (lags) y estadísticas móviles para series de tiempo de precio.

Los lags capturan la autocorrelación del precio de bolsa:
  - lag_1h:   precio de la hora anterior (correlación ~0.95 en el corto plazo)
  - lag_24h:  mismo bloque horario del día anterior (patrón diario)
  - lag_168h: mismo bloque horario de la semana anterior (patrón semanal)
"""
from __future__ import annotations

import pandas as pd


def add_lag_features(
    df: pd.DataFrame,
    price_col: str = "spot_price_cop",
    demand_col: str = "demand_mwh",
    hydrology_col: str = "hydrology_pct",
    sort_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Agrega lags y rolling stats al DataFrame.
    Requiere que el DataFrame esté ordenado por timestamp (o sort_col).
    Los primeros N registros tendrán NaN en los lags correspondientes.
    """
    df = df.sort_values(sort_col).copy()

    # -- Lags de precio --
    df["spot_price_lag_1h"] = df[price_col].shift(1)
    df["spot_price_lag_2h"] = df[price_col].shift(2)
    df["spot_price_lag_3h"] = df[price_col].shift(3)
    df["spot_price_lag_24h"] = df[price_col].shift(24)
    df["spot_price_lag_48h"] = df[price_col].shift(48)
    df["spot_price_lag_168h"] = df[price_col].shift(168)   # 1 semana

    # -- Rolling stats de precio --
    df["spot_price_rolling_mean_6h"] = df[price_col].rolling(6, min_periods=3).mean()
    df["spot_price_rolling_mean_24h"] = df[price_col].rolling(24, min_periods=12).mean()
    df["spot_price_rolling_mean_168h"] = df[price_col].rolling(168, min_periods=48).mean()
    df["spot_price_rolling_std_24h"] = df[price_col].rolling(24, min_periods=12).std()
    df["spot_price_rolling_max_24h"] = df[price_col].rolling(24, min_periods=12).max()
    df["spot_price_rolling_min_24h"] = df[price_col].rolling(24, min_periods=12).min()

    # -- Diferencia de precio (velocidad de cambio) --
    df["spot_price_diff_1h"] = df[price_col].diff(1)
    df["spot_price_diff_24h"] = df[price_col].diff(24)

    # -- Lags de demanda --
    if demand_col in df.columns:
        df["demand_lag_1h"] = df[demand_col].shift(1)
        df["demand_lag_24h"] = df[demand_col].shift(24)
        df["demand_rolling_mean_24h"] = df[demand_col].rolling(24, min_periods=12).mean()

    # -- Rolling de hidrología (varía lento — ventana más larga) --
    if hydrology_col in df.columns:
        df["hydrology_rolling_mean_7d"] = df[hydrology_col].rolling(168, min_periods=24).mean()
        df["hydrology_trend_7d"] = df[hydrology_col] - df["hydrology_rolling_mean_7d"]

    return df


def prepare_prediction_features(
    historical_df: pd.DataFrame,
    future_timestamps: pd.DatetimeIndex,
    price_col: str = "spot_price_cop",
) -> pd.DataFrame:
    """
    Prepara features de lag para las horas futuras a predecir.
    Usa los valores históricos reales para llenar los lags hacia adelante.

    historical_df: datos reales hasta el momento actual
    future_timestamps: timestamps de las próximas 24 horas a predecir
    """
    # Añadir filas vacías para el futuro
    future_rows = pd.DataFrame({"timestamp": future_timestamps})
    future_rows[price_col] = float("nan")   # precio futuro = desconocido

    combined = pd.concat([historical_df, future_rows], ignore_index=True)
    combined = add_lag_features(combined, price_col=price_col)

    # Retornar solo las filas futuras con sus features ya calculadas
    return combined[combined["timestamp"].isin(future_timestamps)].copy()
