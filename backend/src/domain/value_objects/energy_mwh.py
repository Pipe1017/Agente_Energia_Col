from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnergyMWh:
    """Cantidad de energía en megavatios-hora. Inmutable y validada."""

    value: float  # MWh

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"La energía no puede ser negativa: {self.value}")

    def __add__(self, other: EnergyMWh) -> EnergyMWh:
        return EnergyMWh(self.value + other.value)

    def __sub__(self, other: EnergyMWh) -> EnergyMWh:
        if other.value > self.value:
            raise ValueError("Resta de energía resultaría en valor negativo")
        return EnergyMWh(self.value - other.value)

    def __mul__(self, factor: float) -> EnergyMWh:
        return EnergyMWh(self.value * factor)

    def __lt__(self, other: EnergyMWh) -> bool:
        return self.value < other.value

    def __le__(self, other: EnergyMWh) -> bool:
        return self.value <= other.value

    def __gt__(self, other: EnergyMWh) -> bool:
        return self.value > other.value

    def __ge__(self, other: EnergyMWh) -> bool:
        return self.value >= other.value

    def __str__(self) -> str:
        return f"{self.value:,.1f} MWh"

    def to_gwh(self) -> float:
        return self.value / 1000.0

    def to_kwh(self) -> float:
        return self.value * 1000.0

    @classmethod
    def zero(cls) -> EnergyMWh:
        return cls(0.0)
