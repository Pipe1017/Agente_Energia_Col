"""
Interfaz base para todos los modelos de predicción de energía.

Regla: cualquier modelo nuevo = clase que extienda BaseEnergyModel.
El sistema (DAGs, registry, API) no necesita saber nada más.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class BaseEnergyModel(ABC):

    # ------------------------------------------------------------------
    # Propiedades de identidad (deben ser constantes en la clase hija)
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador único del modelo. Ej: 'xgboost', 'lstm', 'prophet'"""
        ...

    @property
    @abstractmethod
    def task(self) -> str:
        """Tarea de predicción. Ej: 'price_prediction_24h', 'demand_forecast'"""
        ...

    @property
    @abstractmethod
    def feature_schema(self) -> list[str]:
        """
        Lista exacta y ordenada de nombres de columnas que el modelo requiere.
        El pipeline de features debe producir exactamente estas columnas.
        """
        ...

    @property
    def version(self) -> str:
        """Versión semántica. Override en la clase concreta si se necesita."""
        return "1.0.0"

    # ------------------------------------------------------------------
    # Ciclo de vida del modelo
    # ------------------------------------------------------------------

    @abstractmethod
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Entrena el modelo. Modifica el estado interno (self).
        X_train debe contener exactamente las columnas de feature_schema.
        y_train: precios reales (COP/kWh) para el período de entrenamiento.
        """
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predicción puntual.
        Retorna array de shape (n_samples,) con precios COP/kWh.
        """
        ...

    @abstractmethod
    def predict_with_intervals(
        self,
        X: pd.DataFrame,
        confidence: float = 0.90,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predicción con intervalos de confianza.
        Retorna: (predictions, lower_bound, upper_bound)
        Cada array tiene shape (n_samples,).
        """
        ...

    @abstractmethod
    def save(self, directory: Path) -> None:
        """
        Guarda el modelo en `directory`.
        Debe crear al menos:
          - model.joblib   (artefacto del modelo)
          - metadata.json  (métricas, params, feature_schema_hash)
        """
        ...

    @classmethod
    @abstractmethod
    def load(cls, directory: Path) -> "BaseEnergyModel":
        """Carga un modelo previamente guardado con save()."""
        ...

    @abstractmethod
    def get_feature_importance(self) -> dict[str, float]:
        """
        Retorna importancia de cada feature normalizada a [0, 1].
        Clave: nombre de feature. Valor: importancia relativa.
        """
        ...

    # ------------------------------------------------------------------
    # Validación — compartida por todas las implementaciones
    # ------------------------------------------------------------------

    def validate_features(self, X: pd.DataFrame) -> None:
        """Lanza ValueError si X no tiene las columnas requeridas."""
        missing = set(self.feature_schema) - set(X.columns)
        if missing:
            raise ValueError(
                f"[{self.name}] Features faltantes: {sorted(missing)}\n"
                f"Requeridas: {self.feature_schema}\n"
                f"Recibidas:  {list(X.columns)}"
            )

    def select_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Selecciona y ordena solo las columnas del feature_schema."""
        self.validate_features(X)
        return X[self.feature_schema].copy()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} task={self.task} v{self.version}>"
