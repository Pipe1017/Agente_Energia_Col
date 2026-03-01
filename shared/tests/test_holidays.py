"""
Tests de festivos colombianos.
La precisión del calendario impacta directamente la calidad del modelo ML.
"""
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

from shared.constants.colombia_holidays import (
    _easter,
    get_day_type,
    get_holidays,
    is_holiday,
    is_working_day,
)


class TestEaster:
    def test_2024(self):
        assert _easter(2024) == date(2024, 3, 31)

    def test_2025(self):
        assert _easter(2025) == date(2025, 4, 20)

    def test_2026(self):
        assert _easter(2026) == date(2026, 4, 5)


class TestFixedHolidays:
    def test_new_year(self):
        assert is_holiday(date(2026, 1, 1))

    def test_labor_day(self):
        assert is_holiday(date(2026, 5, 1))

    def test_independence(self):
        assert is_holiday(date(2026, 7, 20))

    def test_boyaca_battle(self):
        assert is_holiday(date(2026, 8, 7))

    def test_immaculate_conception(self):
        assert is_holiday(date(2026, 12, 8))

    def test_christmas(self):
        assert is_holiday(date(2026, 12, 25))


class TestEasterHolidays:
    """Semana Santa 2026: Pascua = 5 abril → Jueves Santo 2 abril, Viernes Santo 3 abril."""

    def test_holy_thursday_2026(self):
        assert is_holiday(date(2026, 4, 2))

    def test_good_friday_2026(self):
        assert is_holiday(date(2026, 4, 3))

    def test_holy_thursday_2025(self):
        # Pascua 2025 = 20 abril → Jueves Santo = 17 abril
        assert is_holiday(date(2025, 4, 17))

    def test_good_friday_2025(self):
        assert is_holiday(date(2025, 4, 18))


class TestPuenteHolidays:
    """Ley 51/83: si el festivo no cae en lunes, se traslada al siguiente lunes."""

    def test_reyes_magos_2026(self):
        # 6 enero 2026 = martes → traslado a lunes 12 enero
        assert is_holiday(date(2026, 1, 12))
        assert not is_holiday(date(2026, 1, 6))

    def test_san_jose_2026(self):
        # 19 marzo 2026 = jueves → traslado a lunes 23 marzo
        assert is_holiday(date(2026, 3, 23))
        assert not is_holiday(date(2026, 3, 19))

    def test_dia_de_la_raza_2025(self):
        # 12 octubre 2025 = domingo → traslado a lunes 13 octubre
        assert is_holiday(date(2025, 10, 13))


class TestWorkingDays:
    def test_regular_monday_is_working(self):
        # 2 marzo 2026 = lunes, no festivo
        assert is_working_day(date(2026, 3, 2))

    def test_saturday_is_not_working(self):
        assert not is_working_day(date(2026, 3, 7))

    def test_sunday_is_not_working(self):
        assert not is_working_day(date(2026, 3, 8))

    def test_holiday_is_not_working(self):
        assert not is_working_day(date(2026, 1, 1))


class TestDayType:
    def test_laboral(self):
        assert get_day_type(date(2026, 3, 2)) == "laboral"

    def test_sabado(self):
        assert get_day_type(date(2026, 3, 7)) == "sabado"

    def test_domingo(self):
        assert get_day_type(date(2026, 3, 8)) == "domingo"

    def test_festivo(self):
        assert get_day_type(date(2026, 1, 1)) == "festivo"


class TestHolidayCount:
    def test_colombia_has_18_holidays_per_year(self):
        """Colombia tiene 18 días festivos según Ley 51/83."""
        holidays_2026 = get_holidays(2026)
        assert len(holidays_2026) == 18, (
            f"Se esperaban 18 festivos, se encontraron {len(holidays_2026)}: "
            f"{sorted(holidays_2026)}"
        )

    def test_no_duplicate_dates(self):
        holidays = get_holidays(2025)
        assert len(holidays) == len(set(holidays))
