"""
Features de rezago (lags) y estadísticas móviles para series de tiempo de precio.

Los lags capturan la autocorrelación del precio de bolsa:
  - lag_1h:   precio de la hora anterior (correlación ~0.95 en el corto plazo)
  - lag_24h:  mismo bloque horario del día anterior (patrón diario)
  - lag_168h: mismo bloque horario de la semana anterior (patrón semanal)

Variables derivadas clave (del análisis exploratorio):
  - ratio_termico_hidro: Termica / (Hidraulica + 1) — driver principal del precio
  - precio_escasez_spread: precio_bolsa - precio_escasez — señal de activación de escasez
"""
from __future__ import annotations

import pandas as pd


def add_lag_features(
    df: pd.DataFrame,
    price_col: str = "spot_price_cop",
    demand_col: str = "demand_mwh",
    hydrology_col: str = "hydrology_pct",
    reservoir_col: str = "reservoir_level_pct",
    sort_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Agrega lags, rolling stats y variables derivadas al DataFrame.
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

    # -- Rolling de hidrología (varía lento — ventanas corta, media y larga) --
    if hydrology_col in df.columns:
        df["hydrology_rolling_mean_7d"]  = df[hydrology_col].rolling(168,  min_periods=24).mean()
        df["hydrology_trend_7d"]         = df[hydrology_col] - df["hydrology_rolling_mean_7d"]

        # Ventanas largas: señal de sequía / El Niño (requieren historial)
        df["hydrology_rolling_mean_30d"] = df[hydrology_col].rolling(720,  min_periods=168).mean()
        df["hydrology_rolling_mean_90d"] = df[hydrology_col].rolling(2160, min_periods=336).mean()

        # Tendencia hidrológica: positivo = mejorando respecto a trimestre
        # Negativo = empeorando (señal de sequía inminente → precios al alza)
        df["hydrology_trend_30d"] = (
            df["hydrology_rolling_mean_30d"] - df["hydrology_rolling_mean_90d"]
        )

    # -- Lags de nivel de embalse (otro indicador hídrico lento) --
    if reservoir_col in df.columns:
        df["reservoir_lag_24h"] = df[reservoir_col].shift(24)
        df["reservoir_rolling_mean_7d"] = df[reservoir_col].rolling(168, min_periods=24).mean()

    # -- Percentil de precio en distribución histórica --
    # price_percentile_30d ≈ 1.0 → precio alto vs. último mes (señal de tensión)
    # price_percentile_365d ≈ 1.0 → precio alto en contexto anual
    df["price_percentile_30d"]  = (
        df[price_col].rolling(720,  min_periods=168).rank(pct=True)
    )
    df["price_percentile_365d"] = (
        df[price_col].rolling(8760, min_periods=720).rank(pct=True)
    )

    # -- Ratio Térmico/Hidráulico (key driver según análisis SIMEM) --
    # Termica / (Hidraulica + 1) — evita división por cero
    if "gen_termica_gwh" in df.columns and "gen_hidraulica_gwh" in df.columns:
        hidro = df["gen_hidraulica_gwh"].fillna(0)
        term = df["gen_termica_gwh"].fillna(0)
        df["ratio_termico_hidro"] = term / (hidro + 1.0)
        df["ratio_termico_hidro_lag_24h"] = df["ratio_termico_hidro"].shift(24)
        df["ratio_termico_hidro_rolling_7d"] = df["ratio_termico_hidro"].rolling(168, min_periods=24).mean()

    # -- Spread precio vs precio de escasez (señal regulatoria) --
    if "precio_escasez_cop" in df.columns:
        # Forward-fill: el precio de escasez es diario, se aplica a todas las horas
        escasez = df["precio_escasez_cop"].ffill()
        df["precio_escasez_cop_ff"] = escasez
        df["precio_escasez_spread"] = df[price_col] - escasez  # >0 → precio sobre escasez

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
    future_rows = pd.DataFrame({"timestamp": future_timestamps})
    future_rows[price_col] = float("nan")   # precio futuro = desconocido

    combined = pd.concat([historical_df, future_rows], ignore_index=True)
    combined = add_lag_features(combined, price_col=price_col)

    return combined[combined["timestamp"].isin(future_timestamps)].copy()
