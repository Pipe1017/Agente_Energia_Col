"""
Festivos nacionales de Colombia — Ley 51 de 1983 y Ley 27 de 1992.

La demanda eléctrica en días festivos cae entre 15–30% vs día laboral,
impactando directamente el precio de bolsa. Este módulo provee la
lógica de calendario como feature de entrada al modelo ML.

Tipos de festivo:
  - Fijo: siempre la misma fecha (Año Nuevo, Navidad, etc.)
  - Puente: se traslada al lunes siguiente (Ley 51/83)
  - Pascua: depende de la fecha de Semana Santa del año
"""
from __future__ import annotations

from datetime import date, timedelta


# ------------------------------------------------------------------
# Cálculo de Pascua — algoritmo de Meeus/Jones/Butcher
# ------------------------------------------------------------------
def _easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _next_monday(d: date) -> date:
    """Retorna d si ya es lunes, o el siguiente lunes (Ley Puente)."""
    days_ahead = (7 - d.weekday()) % 7  # weekday: 0=lun, 6=dom
    return d if days_ahead == 0 else d + timedelta(days=days_ahead)


# ------------------------------------------------------------------
# Festivos del año
# ------------------------------------------------------------------
def get_holidays(year: int) -> set[date]:
    """
    Retorna el conjunto de fechas festivas nacionales para el año dado.
    Aplica la Ley Puente (traslado al lunes) según Ley 51/83.
    """
    easter = _easter(year)
    holidays: set[date] = set()

    # ---- Festivos FIJOS (no se trasladan) ----
    holidays.update([
        date(year, 1, 1),    # Año Nuevo
        date(year, 5, 1),    # Día del Trabajo
        date(year, 7, 20),   # Independencia de Colombia
        date(year, 8, 7),    # Batalla de Boyacá
        date(year, 12, 8),   # Inmaculada Concepción
        date(year, 12, 25),  # Navidad
    ])

    # ---- Festivos de PASCUA (no se trasladan) ----
    holidays.update([
        easter - timedelta(days=3),   # Jueves Santo
        easter - timedelta(days=2),   # Viernes Santo
    ])

    # ---- Festivos con LEY PUENTE (traslado al lunes) ----
    puente_dates = [
        date(year, 1, 6),    # Reyes Magos
        date(year, 3, 19),   # San José
        date(year, 6, 29),   # San Pedro y San Pablo
        date(year, 8, 15),   # Asunción de la Virgen
        date(year, 10, 12),  # Día de la Raza
        date(year, 11, 1),   # Todos los Santos
        date(year, 11, 11),  # Independencia de Cartagena
    ]
    for d in puente_dates:
        holidays.add(_next_monday(d))

    # ---- Festivos de PASCUA con LEY PUENTE ----
    easter_based = [
        easter + timedelta(days=39),  # Ascensión del Señor
        easter + timedelta(days=60),  # Corpus Christi
        easter + timedelta(days=68),  # Sagrado Corazón de Jesús
    ]
    for d in easter_based:
        holidays.add(_next_monday(d))

    return holidays


def is_holiday(d: date) -> bool:
    return d in get_holidays(d.year)


def is_working_day(d: date) -> bool:
    """True si es día laboral (no festivo y no fin de semana)."""
    return d.weekday() < 5 and not is_holiday(d)


def get_day_type(d: date) -> str:
    """
    Clasifica el día para el modelo ML.
    La demanda eléctrica varía significativamente por tipo de día.
    """
    if is_holiday(d):
        return "festivo"
    if d.weekday() == 5:
        return "sabado"
    if d.weekday() == 6:
        return "domingo"
    return "laboral"


def count_working_days_in_month(year: int, month: int) -> int:
    """Días laborales en el mes — útil para normalizar demanda mensual."""
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    return sum(
        1 for day in range(1, days_in_month + 1)
        if is_working_day(date(year, month, day))
    )


# ------------------------------------------------------------------
# Features derivadas para el modelo ML
# ------------------------------------------------------------------
def get_calendar_features(d: date) -> dict[str, int | float | str]:
    """
    Genera todas las features de calendario para una fecha dada.
    Estas features son inputs directos al modelo de predicción.
    """
    holidays_year = get_holidays(d.year)

    # ¿Es víspera de festivo? La demanda cae la tarde anterior.
    tomorrow = d + timedelta(days=1)
    is_pre_holiday = tomorrow in holidays_year

    # ¿Es post-festivo? La demanda recupera lentamente.
    yesterday = d - timedelta(days=1)
    is_post_holiday = yesterday in holidays_year or yesterday.weekday() == 6

    return {
        "hour_of_day": d.timetuple().tm_hour if hasattr(d, "hour") else 0,
        "day_of_week": d.weekday(),          # 0=lun, 6=dom
        "day_of_month": d.day,
        "month": d.month,
        "week_of_year": d.isocalendar()[1],
        "is_holiday": int(is_holiday(d)),
        "is_weekend": int(d.weekday() >= 5),
        "is_working_day": int(is_working_day(d)),
        "is_pre_holiday": int(is_pre_holiday),
        "is_post_holiday": int(is_post_holiday),
        "day_type": get_day_type(d),          # "laboral" | "sabado" | "domingo" | "festivo"
    }
