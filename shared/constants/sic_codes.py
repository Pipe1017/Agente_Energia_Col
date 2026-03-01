"""
Códigos SIC de agentes generadores registrados en XM.

IMPORTANTE: Verificar contra el RNAC (Registro Nacional de Agentes y Comercializadores)
publicado por XM en:  https://www.xm.com.co/gestión/registro-de-agentes

Estos códigos son los filtros que se usan en la API pydataxm:
    api.request_data("GeneracionReal", "Agente", start, end, filter=["EPMC"])
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentType(str, Enum):
    HYDRO = "hidro"
    THERMAL = "termica"
    WIND = "eolica"
    SOLAR = "solar"
    MIXED = "mixta"       # portafolio con varios tipos


@dataclass(frozen=True)
class KnownAgent:
    sic_code: str
    name: str
    agent_type: AgentType
    department: str           # departamento principal de operación
    installed_capacity_mw: float | None = None   # referencia, no oficial


# ------------------------------------------------------------------
# Agentes principales del mercado eléctrico colombiano
# Fuente: RNAC XM + informes SUI SSPD
# ⚠️  Validar códigos contra RNAC antes de usar en producción
# ------------------------------------------------------------------
KNOWN_AGENTS: dict[str, KnownAgent] = {
    "EPMC": KnownAgent(
        sic_code="EPMC",
        name="Empresas Públicas de Medellín (EPM)",
        agent_type=AgentType.MIXED,
        department="Antioquia",
        installed_capacity_mw=3300.0,
    ),
    "CLSI": KnownAgent(
        sic_code="CLSI",
        name="Celsia S.A. E.S.P.",
        agent_type=AgentType.MIXED,
        department="Valle del Cauca",
        installed_capacity_mw=1500.0,
    ),
    "EMGS": KnownAgent(
        sic_code="EMGS",
        name="Emgesa S.A. E.S.P. (Enel Colombia)",
        agent_type=AgentType.MIXED,
        department="Cundinamarca",
        installed_capacity_mw=2900.0,
    ),
    "ISAG": KnownAgent(
        sic_code="ISAG",
        name="Isagen S.A. E.S.P.",
        agent_type=AgentType.HYDRO,
        department="Antioquia",
        installed_capacity_mw=3032.0,
    ),
    "AESC": KnownAgent(
        sic_code="AESC",
        name="AES Colombia (Chivor)",
        agent_type=AgentType.HYDRO,
        department="Boyacá",
        installed_capacity_mw=1000.0,
    ),
    "GNCL": KnownAgent(
        sic_code="GNCL",
        name="Gecelca S.A. E.S.P.",
        agent_type=AgentType.THERMAL,
        department="Córdoba",
        installed_capacity_mw=830.0,
    ),
    "TEBSA": KnownAgent(
        sic_code="TEBSA",
        name="Termobarranquilla S.A.",
        agent_type=AgentType.THERMAL,
        department="Atlántico",
        installed_capacity_mw=1957.0,
    ),
    "CORG": KnownAgent(
        sic_code="CORG",
        name="Essa / Electrificadora de Santander",
        agent_type=AgentType.HYDRO,
        department="Santander",
    ),
}


def get_agent(sic_code: str) -> KnownAgent | None:
    """Busca un agente conocido por su código SIC (case-insensitive)."""
    return KNOWN_AGENTS.get(sic_code.strip().upper())


def get_all_sic_codes() -> list[str]:
    return list(KNOWN_AGENTS.keys())


def get_agents_by_type(agent_type: AgentType) -> list[KnownAgent]:
    return [a for a in KNOWN_AGENTS.values() if a.agent_type == agent_type]


def is_known_agent(sic_code: str) -> bool:
    return sic_code.strip().upper() in KNOWN_AGENTS
