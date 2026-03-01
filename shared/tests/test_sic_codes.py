import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

from shared.constants.sic_codes import (
    AgentType,
    get_agent,
    get_agents_by_type,
    get_all_sic_codes,
    is_known_agent,
)


class TestSicCodes:
    def test_epm_exists(self):
        agent = get_agent("EPMC")
        assert agent is not None
        assert agent.name.startswith("Empresas Públicas")

    def test_case_insensitive(self):
        assert get_agent("epmc") is not None
        assert get_agent("EPMC") is not None

    def test_unknown_agent_returns_none(self):
        assert get_agent("XXXX") is None

    def test_is_known_agent(self):
        assert is_known_agent("EPMC")
        assert not is_known_agent("FAKE")

    def test_get_all_codes_returns_list(self):
        codes = get_all_sic_codes()
        assert isinstance(codes, list)
        assert len(codes) >= 5
        assert "EPMC" in codes

    def test_get_agents_by_type_hydro(self):
        hydro = get_agents_by_type(AgentType.HYDRO)
        assert len(hydro) >= 1
        assert all(a.agent_type == AgentType.HYDRO for a in hydro)

    def test_all_agents_have_valid_sic_codes(self):
        codes = get_all_sic_codes()
        for code in codes:
            assert code == code.upper(), f"Código no normalizado: {code}"
            assert code.isalnum(), f"Código con caracteres inválidos: {code}"
