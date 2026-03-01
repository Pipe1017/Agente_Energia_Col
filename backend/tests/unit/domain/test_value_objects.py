import pytest

from src.domain.value_objects import EnergyMWh, Price, SICCode


class TestPrice:
    def test_creation(self):
        p = Price(280.5)
        assert p.value == 280.5

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            Price(-1.0)

    def test_zero_is_valid(self):
        assert Price(0.0).value == 0.0

    def test_addition(self):
        assert (Price(100.0) + Price(50.0)).value == 150.0

    def test_subtraction(self):
        assert (Price(100.0) - Price(30.0)).value == 70.0

    def test_multiplication(self):
        assert (Price(100.0) * 2).value == 200.0

    def test_comparison(self):
        assert Price(100.0) < Price(200.0)
        assert Price(200.0) > Price(100.0)
        assert Price(100.0) == Price(100.0)

    def test_immutable(self):
        p = Price(100.0)
        with pytest.raises((AttributeError, TypeError)):
            p.value = 200.0  # type: ignore

    def test_str(self):
        assert "COP" in str(Price(280.5))


class TestEnergyMWh:
    def test_creation(self):
        e = EnergyMWh(1000.0)
        assert e.value == 1000.0

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            EnergyMWh(-1.0)

    def test_to_gwh(self):
        assert EnergyMWh(1000.0).to_gwh() == 1.0

    def test_to_kwh(self):
        assert EnergyMWh(1.0).to_kwh() == 1000.0

    def test_subtraction_below_zero_raises(self):
        with pytest.raises(ValueError):
            EnergyMWh(10.0) - EnergyMWh(20.0)


class TestSICCode:
    def test_creation_and_normalization(self):
        sic = SICCode("epmc")
        assert sic.value == "EPMC"

    def test_whitespace_stripped(self):
        sic = SICCode("  CLSI  ")
        assert sic.value == "CLSI"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            SICCode("")

    def test_special_chars_raise(self):
        with pytest.raises(ValueError):
            SICCode("EP-MC")

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            SICCode("E")

    def test_equality_with_string(self):
        assert SICCode("EPMC") == "epmc"
        assert SICCode("EPMC") == "EPMC"

    def test_immutable(self):
        sic = SICCode("EPMC")
        with pytest.raises((AttributeError, TypeError)):
            sic.value = "OTHER"  # type: ignore

    def test_hashable(self):
        sic_set = {SICCode("EPMC"), SICCode("CLSI"), SICCode("epmc")}
        assert len(sic_set) == 2
