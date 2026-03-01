from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    """Precio de energía en COP por kWh. Inmutable y validado."""

    value: float  # COP/kWh

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"El precio no puede ser negativo: {self.value}")

    def __add__(self, other: Price) -> Price:
        return Price(self.value + other.value)

    def __sub__(self, other: Price) -> Price:
        return Price(self.value - other.value)

    def __mul__(self, factor: float) -> Price:
        return Price(self.value * factor)

    def __lt__(self, other: Price) -> bool:
        return self.value < other.value

    def __le__(self, other: Price) -> bool:
        return self.value <= other.value

    def __gt__(self, other: Price) -> bool:
        return self.value > other.value

    def __ge__(self, other: Price) -> bool:
        return self.value >= other.value

    def __str__(self) -> str:
        return f"COP ${self.value:,.2f}/kWh"

    @classmethod
    def zero(cls) -> Price:
        return cls(0.0)
