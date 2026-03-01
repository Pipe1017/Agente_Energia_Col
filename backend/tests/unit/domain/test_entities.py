import uuid
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc)

import pytest

from src.domain.entities import (
    Agent,
    HourlyOffer,
    HourlyPrice,
    MarketSnapshot,
    ModelStage,
    ModelVersion,
    PricePrediction,
    Recommendation,
    RiskLevel,
    RiskProfile,
)
from src.domain.value_objects import SICCode


def make_hourly_prices(n: int = 24) -> list[HourlyPrice]:
    base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    return [
        HourlyPrice(
            target_hour=base.replace(hour=i),
            predicted_cop=280.0 + i * 2,
            lower_bound_cop=260.0 + i * 2,
            upper_bound_cop=300.0 + i * 2,
            confidence=0.85,
        )
        for i in range(n)
    ]


class TestAgent:
    def test_creation(self):
        agent = Agent(
            id=uuid.uuid4(),
            name="EPM",
            sic_code=SICCode("EPMC"),
        )
        assert agent.name == "EPM"
        assert str(agent.sic_code) == "EPMC"

    def test_is_not_configured_without_capacity(self):
        agent = Agent(id=uuid.uuid4(), name="EPM", sic_code=SICCode("EPMC"))
        assert not agent.is_configured

    def test_is_configured_with_capacity(self):
        agent = Agent(
            id=uuid.uuid4(),
            name="EPM",
            sic_code=SICCode("EPMC"),
            installed_capacity_mw=2500.0,
        )
        assert agent.is_configured

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Agent(id=uuid.uuid4(), name="  ", sic_code=SICCode("EPMC"))

    def test_negative_capacity_raises(self):
        with pytest.raises(ValueError):
            Agent(
                id=uuid.uuid4(),
                name="EPM",
                sic_code=SICCode("EPMC"),
                installed_capacity_mw=-100.0,
            )

    def test_display_name(self):
        agent = Agent(id=uuid.uuid4(), name="EPM", sic_code=SICCode("EPMC"))
        assert "EPM" in agent.display_name
        assert "EPMC" in agent.display_name

    def test_default_risk_profile(self):
        agent = Agent(id=uuid.uuid4(), name="EPM", sic_code=SICCode("EPMC"))
        assert agent.risk_profile == RiskProfile.MODERATE


class TestMarketSnapshot:
    def test_creation(self):
        snap = MarketSnapshot(
            id=uuid.uuid4(),
            timestamp=NOW,
            spot_price_cop=295.0,
            demand_mwh=68400.0,
            hydrology_pct=84.0,
            reservoir_level_pct=62.0,
            thermal_dispatch_pct=18.0,
        )
        assert snap.spot_price_cop == 295.0

    def test_hydrology_critical(self):
        snap = MarketSnapshot(
            id=uuid.uuid4(),
            timestamp=NOW,
            spot_price_cop=350.0,
            demand_mwh=68400.0,
            hydrology_pct=45.0,
            reservoir_level_pct=28.0,
            thermal_dispatch_pct=35.0,
        )
        assert snap.is_hydrology_critical
        assert snap.is_reservoir_low
        assert snap.hydrology_status == "crítica"

    def test_hydrology_normal(self):
        snap = MarketSnapshot(
            id=uuid.uuid4(),
            timestamp=NOW,
            spot_price_cop=280.0,
            demand_mwh=65000.0,
            hydrology_pct=95.0,
            reservoir_level_pct=70.0,
            thermal_dispatch_pct=12.0,
        )
        assert not snap.is_hydrology_critical
        assert snap.hydrology_status == "normal"

    def test_invalid_hydrology_pct_raises(self):
        with pytest.raises(ValueError):
            MarketSnapshot(
                id=uuid.uuid4(),
                timestamp=NOW,
                spot_price_cop=280.0,
                demand_mwh=65000.0,
                hydrology_pct=400.0,  # fuera de rango
                reservoir_level_pct=70.0,
                thermal_dispatch_pct=12.0,
            )


class TestPricePrediction:
    def test_creation(self):
        pred = PricePrediction(
            id=uuid.uuid4(),
            agent_sic_code="EPMC",
            generated_at=NOW,
            model_version_id=uuid.uuid4(),
            horizon_hours=24,
            hourly_predictions=make_hourly_prices(24),
            overall_confidence=0.85,
        )
        assert len(pred.hourly_predictions) == 24

    def test_wrong_count_raises(self):
        with pytest.raises(ValueError):
            PricePrediction(
                id=uuid.uuid4(),
                agent_sic_code="EPMC",
                generated_at=NOW,
                model_version_id=uuid.uuid4(),
                horizon_hours=24,
                hourly_predictions=make_hourly_prices(12),  # solo 12
                overall_confidence=0.85,
            )

    def test_avg_price(self):
        pred = PricePrediction(
            id=uuid.uuid4(),
            agent_sic_code="EPMC",
            generated_at=NOW,
            model_version_id=uuid.uuid4(),
            horizon_hours=24,
            hourly_predictions=make_hourly_prices(24),
            overall_confidence=0.85,
        )
        assert pred.avg_predicted_price > 0

    def test_peak_hours_detection(self):
        pred = PricePrediction(
            id=uuid.uuid4(),
            agent_sic_code="EPMC",
            generated_at=NOW,
            model_version_id=uuid.uuid4(),
            horizon_hours=24,
            hourly_predictions=make_hourly_prices(24),
            overall_confidence=0.85,
        )
        # horas 18-21 son pico
        assert len(pred.peak_predictions) == 4


class TestModelVersion:
    def test_is_better_than(self):
        m1 = ModelVersion(
            id=uuid.uuid4(),
            task="price_prediction_24h",
            model_name="xgboost",
            version="1.1.0",
            stage=ModelStage.STAGING,
            artifact_path="models/price_prediction_24h/xgboost/1.1.0/",
            metrics={"rmse": 10.0, "mae": 7.0, "mape": 3.5},
            params={},
            is_champion=False,
            trained_at=NOW,
            trained_on_days=90,
        )
        m2 = ModelVersion(
            id=uuid.uuid4(),
            task="price_prediction_24h",
            model_name="xgboost",
            version="1.0.0",
            stage=ModelStage.PRODUCTION,
            artifact_path="models/price_prediction_24h/xgboost/1.0.0/",
            metrics={"rmse": 12.3, "mae": 8.1, "mape": 4.2},
            params={},
            is_champion=True,
            trained_at=NOW,
            trained_on_days=90,
        )
        assert m1.is_better_than(m2)
        assert not m2.is_better_than(m1)

    def test_champion_must_be_production(self):
        with pytest.raises(ValueError):
            ModelVersion(
                id=uuid.uuid4(),
                task="price_prediction_24h",
                model_name="xgboost",
                version="1.0.0",
                stage=ModelStage.STAGING,  # no es PRODUCTION
                artifact_path="models/...",
                metrics={},
                params={},
                is_champion=True,  # pero dice que es champion → error
                trained_at=NOW,
                trained_on_days=90,
            )
