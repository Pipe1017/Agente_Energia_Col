from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SICCode:
    """
    Código SIC del agente en el mercado eléctrico colombiano.
    Inmutable. Normalizado a mayúsculas.
    Ejemplos válidos: EPMC, CLSI, EMGS, ISAG
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("El código SIC no puede estar vacío")
        normalized = self.value.strip().upper()
        if not normalized.isalnum():
            raise ValueError(
                f"Código SIC inválido '{self.value}': solo caracteres alfanuméricos"
            )
        if len(normalized) < 2 or len(normalized) > 8:
            raise ValueError(
                f"Código SIC inválido '{self.value}': debe tener entre 2 y 8 caracteres"
            )
        # frozen=True → usar object.__setattr__ para normalizar
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SICCode):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other.strip().upper()
        return False

    def __hash__(self) -> int:
        return hash(self.value)
