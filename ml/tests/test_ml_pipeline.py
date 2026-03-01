"""
Tests del pipeline ML con datos sintéticos.
No requiere DB ni MinIO — solo pandas, numpy y xgboost.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.evaluation.champion_challenger import full_comparison_report, should_promote
from ml.evaluation.metrics import coverage_rate, evaluate_all, mae, mape, rmse
from ml.features.feature_pipeline import (
    PRICE_PREDICTION_FEATURES,
    build_feature_matrix,
    get_X_y,
    train_val_split,
)
from ml.models.price_prediction.xgboost_model import XGBoostPriceModel


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def make_market_data(n_hours: int = 500) -> pd.DataFrame:
    """
    Genera datos de mercado sintéticos con patrones realistas.
    Precio base ~280 COP/kWh con ciclo diario, ruido y tendencia.
    """
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    timestamps = [start + timedelta(hours=i) for i in range(n_hours)]

    hours = np.array([t.hour for t in timestamps])
    days = np.arange(n_hours) / 24

    # Precio con patrón diario (pico 18-21h) + semanal + ruido
    price = (
        280
        + 40 * np.sin(2 * np.pi * hours / 24 - np.pi / 2)   # ciclo diario
        + 15 * np.sin(2 * np.pi * days / 7)                   # ciclo semanal
        + np.random.normal(0, 10, n_hours)                     # ruido
    )
    price = np.clip(price, 100, 600)

    demand = (
        65000
        + 8000 * np.sin(2 * np.pi * hours / 24)
        + np.random.normal(0, 2000, n_hours)
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "spot_price_cop": price,
        "demand_mwh": demand,
        "hydrology_pct": np.random.uniform(70, 110, n_hours),
        "reservoir_level_pct": np.random.uniform(40, 80, n_hours),
        "thermal_dispatch_pct": np.random.uniform(10, 30, n_hours),
    })


@pytest.fixture(scope="module")
def market_df():
    np.random.seed(42)
    return make_market_data(600)


@pytest.fixture(scope="module")
def feature_df(market_df):
    return build_feature_matrix(market_df, drop_na=True)


@pytest.fixture(scope="module")
def trained_model(feature_df):
    train_df, val_df = train_val_split(feature_df, val_days=7)
    X_train, y_train = get_X_y(train_df)
    X_val, y_val = get_X_y(val_df)
    model = XGBoostPriceModel()
    model.train(X_train, y_train, X_val=X_val, y_val=y_val)
    return model, X_val, y_val


# ------------------------------------------------------------------
# Tests de feature pipeline
# ------------------------------------------------------------------

class TestFeaturePipeline:
    def test_build_feature_matrix_has_all_features(self, feature_df):
        for feat in PRICE_PREDICTION_FEATURES:
            assert feat in feature_df.columns, f"Feature faltante: {feat}"

    def test_no_nan_in_features_after_build(self, feature_df):
        missing = feature_df[PRICE_PREDICTION_FEATURES].isnull().sum()
        total_missing = missing.sum()
        assert total_missing == 0, f"NaN encontrados:\n{missing[missing > 0]}"

    def test_calendar_features_ranges(self, feature_df):
        assert feature_df["hour_of_day"].between(0, 23).all()
        assert feature_df["day_of_week"].between(0, 6).all()
        assert feature_df["month"].between(1, 12).all()
        assert feature_df["is_holiday"].isin([0, 1]).all()
        assert feature_df["is_weekend"].isin([0, 1]).all()

    def test_cyclic_features_bounded(self, feature_df):
        assert feature_df["sin_hour"].between(-1.01, 1.01).all()
        assert feature_df["cos_hour"].between(-1.01, 1.01).all()

    def test_train_val_split_temporal(self, feature_df):
        train, val = train_val_split(feature_df, val_days=7)
        assert train["timestamp"].max() < val["timestamp"].min()
        assert len(train) > len(val)

    def test_get_X_y_shapes(self, feature_df):
        X, y = get_X_y(feature_df)
        assert X.shape[1] == len(PRICE_PREDICTION_FEATURES)
        assert len(X) == len(y)
        assert not y.isnull().any()


# ------------------------------------------------------------------
# Tests del modelo XGBoost
# ------------------------------------------------------------------

class TestXGBoostModel:
    def test_name_and_task(self):
        model = XGBoostPriceModel()
        assert model.name == "xgboost"
        assert model.task == "price_prediction_24h"

    def test_predict_before_train_raises(self):
        model = XGBoostPriceModel()
        with pytest.raises(RuntimeError):
            model.predict(pd.DataFrame())

    def test_train_and_predict(self, trained_model):
        model, X_val, y_val = trained_model
        preds = model.predict(X_val)
        assert preds.shape == (len(X_val),)
        assert not np.isnan(preds).any()
        assert (preds > 0).all()

    def test_predict_with_intervals(self, trained_model):
        model, X_val, _ = trained_model
        preds, lower, upper = model.predict_with_intervals(X_val)
        assert lower.shape == preds.shape == upper.shape
        # Verificar que los intervalos son coherentes
        assert (lower <= preds).all(), "lower > preds en algún punto"
        assert (upper >= preds).all(), "upper < preds en algún punto"

    def test_feature_importance_sums_to_one(self, trained_model):
        model, _, _ = trained_model
        importance = model.get_feature_importance()
        assert set(importance.keys()) == set(PRICE_PREDICTION_FEATURES)
        total = sum(importance.values())
        assert abs(total - 1.0) < 0.01, f"Importancias no suman 1: {total}"

    def test_validate_features_raises_on_missing(self, trained_model, feature_df):
        model, _, _ = trained_model
        bad_df = feature_df.drop(columns=["hour_of_day"])
        X_bad = bad_df[[c for c in PRICE_PREDICTION_FEATURES if c != "hour_of_day"]]
        with pytest.raises(ValueError, match="Features faltantes"):
            model.predict(X_bad)

    def test_save_and_load(self, trained_model, feature_df):
        model, X_val, _ = trained_model
        preds_before = model.predict(X_val)

        with tempfile.TemporaryDirectory() as tmpdir:
            model.save(Path(tmpdir))
            # Verificar archivos creados
            files = list(Path(tmpdir).iterdir())
            filenames = [f.name for f in files]
            assert "model_mid.joblib" in filenames
            assert "metadata.json" in filenames

            # Cargar y verificar que predice igual
            loaded = XGBoostPriceModel.load(Path(tmpdir))
            preds_after = loaded.predict(X_val)
            np.testing.assert_array_almost_equal(preds_before, preds_after, decimal=4)

    def test_reasonable_rmse(self, trained_model):
        """El RMSE debe ser razonable para datos sintéticos."""
        model, X_val, y_val = trained_model
        preds = model.predict(X_val)
        error = rmse(y_val, preds)
        # Con 500 horas de datos sintéticos esperamos RMSE < 50 COP/kWh
        assert error < 50.0, f"RMSE demasiado alto: {error:.2f}"


# ------------------------------------------------------------------
# Tests de métricas
# ------------------------------------------------------------------

class TestMetrics:
    def test_rmse_perfect(self):
        y = np.array([100.0, 200.0, 300.0])
        assert rmse(y, y) == pytest.approx(0.0, abs=1e-6)

    def test_mae_known_value(self):
        y_true = np.array([100.0, 200.0])
        y_pred = np.array([110.0, 190.0])
        assert mae(y_true, y_pred) == pytest.approx(10.0)

    def test_mape_known_value(self):
        y_true = np.array([100.0, 200.0])
        y_pred = np.array([110.0, 200.0])
        # error: |10/100| = 0.10, |0/200| = 0 → mean = 5%
        assert mape(y_true, y_pred) == pytest.approx(5.0, abs=0.01)

    def test_coverage_rate_perfect(self):
        y = np.array([100.0, 200.0, 300.0])
        lower = y - 10
        upper = y + 10
        assert coverage_rate(y, lower, upper) == pytest.approx(1.0)

    def test_coverage_rate_none(self):
        y = np.array([100.0, 200.0, 300.0])
        lower = y + 20
        upper = y + 30
        assert coverage_rate(y, lower, upper) == pytest.approx(0.0)

    def test_evaluate_all_returns_all_keys(self):
        y = np.random.uniform(200, 400, 100)
        pred = y + np.random.normal(0, 10, 100)
        results = evaluate_all(y, pred)
        assert set(results.keys()) >= {"rmse", "mae", "mape", "r2"}


# ------------------------------------------------------------------
# Tests de champion/challenger
# ------------------------------------------------------------------

class TestChampionChallenger:
    def test_promote_when_challenger_better(self):
        champ = {"rmse": 15.0, "mae": 10.0}
        chall = {"rmse": 12.0, "mae": 8.5}   # 20% mejora
        promote, reason = should_promote(champ, chall, min_improvement_pct=2.0)
        assert promote
        assert "mejora" in reason

    def test_no_promote_when_marginal(self):
        champ = {"rmse": 15.0}
        chall = {"rmse": 14.9}   # solo 0.67% mejora
        promote, _ = should_promote(champ, chall, min_improvement_pct=2.0)
        assert not promote

    def test_no_promote_when_worse(self):
        champ = {"rmse": 12.0}
        chall = {"rmse": 15.0}
        promote, _ = should_promote(champ, chall)
        assert not promote

    def test_full_report_structure(self):
        champ = {"rmse": 15.0, "mae": 10.0, "mape": 5.0, "r2": 0.80}
        chall = {"rmse": 12.0, "mae": 8.0, "mape": 4.0, "r2": 0.85}
        report = full_comparison_report(champ, chall)
        assert "comparison" in report
        assert "decision" in report
        assert report["decision"] == "promote"
