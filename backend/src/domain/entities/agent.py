from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from ..value_objects.sic_code import SICCode


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"  # ofertar por debajo del mercado → despacho seguro
    MODERATE = "moderate"          # balance riesgo/ingreso
    AGGRESSIVE = "aggressive"      # maximizar ingreso, acepta riesgo de no despacho


@dataclass
class Agent:
    """
    Agente generador en el mercado eléctrico colombiano.
    Ejemplos: EPM, Celsia, Emgesa, Isagen, AES Colombia.

    Los campos opcionales se completan en el perfil privado del agente.
    Sin ellos el sistema funciona con datos públicos de XM.
    """

    id: UUID
    name: str                                    # "EPM"
    sic_code: SICCode                            # SICCode("EPMC")
    risk_profile: RiskProfile = RiskProfile.MODERATE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Campos opcionales — enriquecen las recomendaciones del LLM
    resources: list[str] = field(default_factory=list)   # códigos SIC de sus plantas
    installed_capacity_mw: float | None = None            # MW totales instalados
    variable_cost_cop_kwh: float | None = None            # costo variable declarado (privado)

    @property
    def is_configured(self) -> bool:
        """True si el agente cargó sus datos privados opcionales."""
        return self.installed_capacity_mw is not None

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.sic_code})"

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("El nombre del agente no puede estar vacío")
        if self.installed_capacity_mw is not None and self.installed_capacity_mw <= 0:
            raise ValueError("La capacidad instalada debe ser mayor a cero")
        if self.variable_cost_cop_kwh is not None and self.variable_cost_cop_kwh < 0:
            raise ValueError("El costo variable no puede ser negativo")
