"""
Features de calendario para el modelo de predicción de precio.

La demanda eléctrica varía significativamente según:
  - Hora del día (pico industrial 08-12h, pico residencial 18-21h)
  - Día de semana (laborales vs fines de semana)
  - Festivos (caída 15-30% vs día laboral equivalente)
  - Estacionalidad mensual (diciembre/enero = demanda residencial alta)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Permitir import desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parents[3]))
from shared.constants.colombia_holidays import get_holidays


def add_calendar_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    Agrega features de calendario al DataFrame.
    El DataFrame debe tener una columna de timestamps con timezone.

    Columnas agregadas:
      hour_of_day, day_of_week, month, week_of_year,
      is_holiday, is_weekend, is_working_day, is_pre_holiday,
      is_peak_hour, sin_hour, cos_hour, sin_dow, cos_dow
    """
    df = df.copy()
    ts = pd.to_datetime(df[timestamp_col])

    df["hour_of_day"] = ts.dt.hour
    df["day_of_week"] = ts.dt.dayofweek        # 0=lunes, 6=domingo
    df["month"] = ts.dt.month
    df["week_of_year"] = ts.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

    # Festivos Colombia (cache por año)
    _holiday_cache: dict[int, set] = {}

    def _is_holiday(d: pd.Timestamp) -> int:
        year = d.year
        if year not in _holiday_cache:
            _holiday_cache[year] = get_holidays(year)
        return int(d.date() in _holiday_cache[year])

    def _is_pre_holiday(d: pd.Timestamp) -> int:
        tomorrow = (d + pd.Timedelta(days=1)).date()
        year = tomorrow.year
        if year not in _holiday_cache:
            _holiday_cache[year] = get_holidays(year)
        return int(tomorrow in _holiday_cache[year])

    df["is_holiday"] = ts.apply(_is_holiday)
    df["is_pre_holiday"] = ts.apply(_is_pre_holiday)
    df["is_working_day"] = ((df["is_weekend"] == 0) & (df["is_holiday"] == 0)).astype(int)

    # Hora pico Colombia: residencial 18-21h, industrial 08-12h
    df["is_peak_hour"] = ts.dt.hour.isin(range(18, 22)).astype(int)
    df["is_off_peak"] = ts.dt.hour.isin(range(0, 6)).astype(int)

    # Codificación cíclica para hora y día de semana
    # Evita que el modelo piense que hora 23 y hora 0 son muy distintas
    df["sin_hour"] = (2 * 3.14159 * df["hour_of_day"] / 24).apply(pd.np.sin if hasattr(pd, 'np') else __import__('numpy').sin)
    df["cos_hour"] = (2 * 3.14159 * df["hour_of_day"] / 24).apply(__import__('numpy').cos)
    df["sin_dow"] = (2 * 3.14159 * df["day_of_week"] / 7).apply(__import__('numpy').sin)
    df["cos_dow"] = (2 * 3.14159 * df["day_of_week"] / 7).apply(__import__('numpy').cos)

    return df
