"""
Modelo XGBoost para predicción de precio de bolsa en Colombia.

Estrategia de intervalos de confianza:
  Se entrenan 3 modelos con regresión cuantil:
  - q=0.05: límite inferior (percentil 5)
  - q=0.50: predicción central (mediana)
  - q=0.95: límite superior (percentil 95)

  El objetivo 'reg:quantileerror' está disponible en XGBoost >= 2.0.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ..base_model import BaseEnergyModel
from ...features.feature_pipeline import PRICE_PREDICTION_FEATURES

logger = logging.getLogger(__name__)

# Hiperparámetros por defecto — optimizar en notebooks antes de producción
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "tree_method": "hist",     # eficiente en CPU, compatible ARM + x86
    "device": "cpu",           # explícito: sin dependencia de CUDA
    "n_jobs": -1,
    "random_state": 42,
    "early_stopping_rounds": 50,
}


class XGBoostPriceModel(BaseEnergyModel):

    def __init__(self) -> None:
        self._model_mid: XGBRegressor | None = None    # predicción central (q=0.50)
        self._model_low: XGBRegressor | None = None    # límite inferior   (q=0.05)
        self._model_high: XGBRegressor | None = None   # límite superior   (q=0.95)
        self._trained_params: dict[str, Any] = {}
        self._feature_importances: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Identidad
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "xgboost"

    @property
    def task(self) -> str:
        return "price_prediction_24h"

    @property
    def feature_schema(self) -> list[str]:
        return PRICE_PREDICTION_FEATURES

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: dict[str, Any] | None = None,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None,
    ) -> None:
        X_train = self.select_features(X_train)
        merged_params = {**DEFAULT_PARAMS, **(params or {})}
        self._trained_params = merged_params

        eval_set = [(X_val[self.feature_schema], y_val)] if X_val is not None else None
        fit_kwargs: dict[str, Any] = {}
        if eval_set:
            fit_kwargs["eval_set"] = eval_set
            fit_kwargs["verbose"] = 100

        logger.info("Entrenando XGBoost central (q=0.50) con %d muestras...", len(X_train))
        self._model_mid = XGBRegressor(
            **{k: v for k, v in merged_params.items() if k != "early_stopping_rounds"},
            objective="reg:squarederror",
        )
        self._model_mid.fit(X_train, y_train, **fit_kwargs)

        logger.info("Entrenando modelo de límite inferior (q=0.05)...")
        self._model_low = XGBRegressor(
            **{k: v for k, v in merged_params.items() if k != "early_stopping_rounds"},
            objective="reg:quantileerror",
            quantile_alpha=0.05,
        )
        self._model_low.fit(X_train, y_train)

        logger.info("Entrenando modelo de límite superior (q=0.95)...")
        self._model_high = XGBRegressor(
            **{k: v for k, v in merged_params.items() if k != "early_stopping_rounds"},
            objective="reg:quantileerror",
            quantile_alpha=0.95,
        )
        self._model_high.fit(X_train, y_train)

        # Feature importance desde el modelo central
        importances = self._model_mid.feature_importances_
        total = importances.sum() or 1.0
        self._feature_importances = {
            feat: float(imp / total)
            for feat, imp in zip(self.feature_schema, importances)
        }
        logger.info("Entrenamiento completado.")

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------

    def _check_trained(self) -> None:
        if self._model_mid is None:
            raise RuntimeError(f"El modelo '{self.name}' no ha sido entrenado.")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self._check_trained()
        X_sel = self.select_features(X)
        return self._model_mid.predict(X_sel)  # type: ignore[union-attr]

    def predict_with_intervals(
        self,
        X: pd.DataFrame,
        confidence: float = 0.90,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self._check_trained()
        X_sel = self.select_features(X)
        preds = self._model_mid.predict(X_sel)      # type: ignore[union-attr]
        lower = self._model_low.predict(X_sel)      # type: ignore[union-attr]
        upper = self._model_high.predict(X_sel)     # type: ignore[union-attr]
        # Garantizar que lower <= preds <= upper
        lower = np.minimum(lower, preds)
        upper = np.maximum(upper, preds)
        return preds, lower, upper

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def save(self, directory: Path) -> None:
        self._check_trained()
        directory.mkdir(parents=True, exist_ok=True)

        joblib.dump(self._model_mid, directory / "model_mid.joblib")
        joblib.dump(self._model_low, directory / "model_low.joblib")
        joblib.dump(self._model_high, directory / "model_high.joblib")

        metadata = {
            "name": self.name,
            "task": self.task,
            "version": self.version,
            "feature_schema": self.feature_schema,
            "params": self._trained_params,
            "feature_importances": self._feature_importances,
        }
        with open(directory / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Modelo guardado en: %s", directory)

    @classmethod
    def load(cls, directory: Path) -> "XGBoostPriceModel":
        model = cls()
        model._model_mid = joblib.load(directory / "model_mid.joblib")
        model._model_low = joblib.load(directory / "model_low.joblib")
        model._model_high = joblib.load(directory / "model_high.joblib")
        with open(directory / "metadata.json") as f:
            metadata = json.load(f)
        model._trained_params = metadata.get("params", {})
        model._feature_importances = metadata.get("feature_importances", {})
        logger.info("Modelo cargado desde: %s", directory)
        return model

    # ------------------------------------------------------------------
    # Interpretabilidad
    # ------------------------------------------------------------------

    def get_feature_importance(self) -> dict[str, float]:
        self._check_trained()
        return dict(sorted(
            self._feature_importances.items(),
            key=lambda x: x[1],
            reverse=True,
        ))

    def top_features(self, n: int = 10) -> list[tuple[str, float]]:
        return list(self.get_feature_importance().items())[:n]
