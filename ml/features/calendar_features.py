"""
Features de calendario para el modelo de predicción de precio.

La demanda eléctrica varía significativamente según:
  - Hora del día (pico industrial 08-12h, pico residencial 18-21h)
  - Día de semana (laborales vs fines de semana)
  - Festivos (caída 15-30% vs día laboral equivalente)
  - Estacionalidad mensual (diciembre/enero = demanda residencial alta)
  - Estacionalidad anual (ciclos hidrológicos, El Niño/La Niña)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Permitir import desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parents[3]))
from shared.constants.colombia_holidays import get_holidays

# Semestre húmedo Colombia: abril–noviembre
# Semestre seco: diciembre–marzo (precios históricamente más altos)
_WET_MONTHS: frozenset[int] = frozenset(range(4, 12))   # 4,5,...,11


def add_calendar_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    Agrega features de calendario al DataFrame.
    El DataFrame debe tener una columna de timestamps con timezone.

    Columnas agregadas:
      hour_of_day, day_of_week, month, week_of_year,
      is_holiday, is_weekend, is_working_day, is_pre_holiday,
      is_peak_hour, is_off_peak,
      sin_hour, cos_hour, sin_dow, cos_dow,
      sin_doy, cos_doy,           ← ciclo anual (El Niño, temporadas)
      semestre_hidrologico        ← 1=húmedo(abr-nov), 0=seco(dic-mar)
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

    # Codificación cíclica hora y día de semana
    # Evita que el modelo piense que hora 23 y hora 0 son muy distintas
    df["sin_hour"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["cos_hour"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    df["sin_dow"]  = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["cos_dow"]  = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # ---------------------------------------------------------------
    # Ciclo anual: captura estacionalidad de largo plazo
    # (temporadas hidrológicas, El Niño/La Niña, pico dic-ene)
    # ---------------------------------------------------------------
    doy = ts.dt.dayofyear.astype(float)
    df["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    df["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)

    # Semestre hidrológico colombiano
    # Húmedo (1): abril–noviembre → mayor disponibilidad hídrica → precios bajos
    # Seco    (0): diciembre–marzo → termoeléctricas dominan  → precios altos
    df["semestre_hidrologico"] = ts.dt.month.isin(_WET_MONTHS).astype(int)

    return df
