"""
Tests unitarios de los routers FastAPI usando mocks.
No requieren PostgreSQL, Redis ni servicios externos.
Se usa httpx.AsyncClient con app directamente.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.interface.api.main import app
from src.domain.entities.agent import Agent, RiskProfile
from src.domain.entities.market_data import MarketSnapshot
from src.domain.value_objects.sic_code import SICCode


# ------------------------------------------------------------------
# Fixtures compartidos
# ------------------------------------------------------------------

NOW = datetime.now(timezone.utc)

SAMPLE_AGENT = Agent(
    id=uuid.uuid4(),
    name="EPM Ituango",
    sic_code=SICCode("EPMC"),
    risk_profile=RiskProfile.MODERATE,
    installed_capacity_mw=2400.0,
    variable_cost_cop_kwh=None,
    resources=["ITUANGO"],
    created_at=NOW,
)

SAMPLE_SNAPSHOT = MarketSnapshot(
    id=uuid.uuid4(),
    timestamp=NOW,
    spot_price_cop=285.5,
    demand_mwh=65_000.0,
    hydrology_pct=82.0,
    reservoir_level_pct=55.0,
    thermal_dispatch_pct=15.0,
    agent_sic_code=None,
    ingested_at=NOW,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_has_version(self, client):
        r = client.get("/api/v1/health")
        assert "version" in r.json()


# ------------------------------------------------------------------
# Agents router
# ------------------------------------------------------------------

class TestAgentsRouter:
    def test_list_agents_empty(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/agents")
            assert r.status_code == 200
            assert r.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_list_agents_returns_agents(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        mock_repo.get_all = AsyncMock(return_value=[SAMPLE_AGENT])

        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/agents")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 1
            assert data[0]["sic_code"] == "EPMC"
            assert data[0]["name"] == "EPM Ituango"
            assert data[0]["is_configured"] is True
        finally:
            app.dependency_overrides.clear()

    def test_get_agent_not_found(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        mock_repo.get_by_sic = AsyncMock(return_value=None)

        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/agents/XXXX")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_get_agent_found(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        mock_repo.get_by_sic = AsyncMock(return_value=SAMPLE_AGENT)

        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/agents/EPMC")
            assert r.status_code == 200
            assert r.json()["sic_code"] == "EPMC"
        finally:
            app.dependency_overrides.clear()

    def test_create_agent_success(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        mock_repo.get_by_sic = AsyncMock(return_value=None)  # no existe aún
        mock_repo.save = AsyncMock(return_value=SAMPLE_AGENT)

        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.post("/api/v1/agents", json={
                "name": "EPM Ituango",
                "sic_code": "EPMC",
                "risk_profile": "moderate",
            })
            assert r.status_code == 201
        finally:
            app.dependency_overrides.clear()

    def test_create_agent_invalid_risk_profile(self, client):
        from src.interface.api.deps import get_agent_repo
        mock_repo = AsyncMock()
        app.dependency_overrides[get_agent_repo] = lambda: mock_repo
        try:
            r = client.post("/api/v1/agents", json={
                "name": "Test",
                "sic_code": "TEST",
                "risk_profile": "reckless",   # valor inválido
            })
            assert r.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ------------------------------------------------------------------
# Market router
# ------------------------------------------------------------------

class TestMarketRouter:
    def test_get_latest_market_not_found(self, client):
        from src.interface.api.deps import get_market_repo
        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=None)

        app.dependency_overrides[get_market_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/market/latest")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_get_latest_market_success(self, client):
        from src.interface.api.deps import get_market_repo
        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=SAMPLE_SNAPSHOT)

        app.dependency_overrides[get_market_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/market/latest")
            assert r.status_code == 200
            data = r.json()
            assert data["spot_price_cop"] == pytest.approx(285.5, rel=1e-3)
            assert data["hydrology_status"] == SAMPLE_SNAPSHOT.hydrology_status
        finally:
            app.dependency_overrides.clear()

    def test_get_last_n_hours_invalid_range(self, client):
        from src.interface.api.deps import get_market_repo
        mock_repo = AsyncMock()
        app.dependency_overrides[get_market_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/market/last/1000h")
            assert r.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_market_summary_no_data(self, client):
        from src.interface.api.deps import get_market_repo
        mock_repo = AsyncMock()
        mock_repo.get_last_n_hours = AsyncMock(return_value=[])

        app.dependency_overrides[get_market_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/market/summary?hours=24")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_market_summary_calculates_stats(self, client):
        from src.interface.api.deps import get_market_repo
        s1 = MarketSnapshot(
            id=uuid.uuid4(), timestamp=NOW,
            spot_price_cop=300.0, demand_mwh=60000.0,
            hydrology_pct=75.0, reservoir_level_pct=50.0,
            thermal_dispatch_pct=20.0, agent_sic_code=None, ingested_at=NOW,
        )
        s2 = MarketSnapshot(
            id=uuid.uuid4(), timestamp=NOW,
            spot_price_cop=200.0, demand_mwh=70000.0,
            hydrology_pct=75.0, reservoir_level_pct=50.0,
            thermal_dispatch_pct=20.0, agent_sic_code=None, ingested_at=NOW,
        )
        mock_repo = AsyncMock()
        mock_repo.get_last_n_hours = AsyncMock(return_value=[s1, s2])

        app.dependency_overrides[get_market_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/market/summary?hours=2")
            assert r.status_code == 200
            data = r.json()
            assert data["avg_price_cop"] == pytest.approx(250.0)
            assert data["min_price_cop"] == pytest.approx(200.0)
            assert data["max_price_cop"] == pytest.approx(300.0)
        finally:
            app.dependency_overrides.clear()


# ------------------------------------------------------------------
# Models router
# ------------------------------------------------------------------

class TestModelsRouter:
    def test_get_champion_no_champion(self, client):
        from src.interface.api.deps import get_model_repo
        mock_repo = AsyncMock()
        mock_repo.get_champion = AsyncMock(return_value=None)
        mock_repo.get_all_by_task = AsyncMock(return_value=[])

        app.dependency_overrides[get_model_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/models/champion")
            assert r.status_code == 200
            data = r.json()
            assert data["has_champion"] is False
            assert data["champion"] is None
            assert data["total_versions"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_list_versions_invalid_stage(self, client):
        from src.interface.api.deps import get_model_repo
        mock_repo = AsyncMock()
        app.dependency_overrides[get_model_repo] = lambda: mock_repo
        try:
            r = client.get("/api/v1/models/versions?stage=invalid")
            assert r.status_code == 422
        finally:
            app.dependency_overrides.clear()
