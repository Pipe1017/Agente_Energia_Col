from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class HourlyPrice:
    """Predicción de precio para una hora específica con intervalo de confianza."""

    target_hour: datetime
    predicted_cop: float       # COP/kWh — valor central
    lower_bound_cop: float     # límite inferior del intervalo de confianza
    upper_bound_cop: float     # límite superior del intervalo de confianza
    confidence: float          # 0.0 – 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence fuera de rango [0,1]: {self.confidence}")
        if self.lower_bound_cop > self.predicted_cop:
            raise ValueError("lower_bound_cop no puede superar a predicted_cop")
        if self.upper_bound_cop < self.predicted_cop:
            raise ValueError("upper_bound_cop no puede ser menor a predicted_cop")

    @property
    def spread_cop(self) -> float:
        """Amplitud del intervalo de confianza (incertidumbre)."""
        return self.upper_bound_cop - self.lower_bound_cop

    @property
    def is_peak_hour(self) -> bool:
        """Hora pico eléctrico en Colombia: 18–21h."""
        return 18 <= self.target_hour.hour <= 21


@dataclass
class PricePrediction:
    """
    Predicción de precio de bolsa para las próximas N horas.
    Generada por el modelo ML champion de la tarea 'price_prediction_24h'.
    """

    id: UUID
    agent_sic_code: str
    generated_at: datetime
    model_version_id: UUID
    horizon_hours: int                              # típicamente 24
    hourly_predictions: list[HourlyPrice]
    overall_confidence: float                       # promedio ponderado

    # Rellenado después cuando se conoce el precio real (para evaluación)
    actuals: list[HourlyPrice] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.horizon_hours <= 0:
            raise ValueError(f"horizon_hours debe ser positivo: {self.horizon_hours}")
        if len(self.hourly_predictions) != self.horizon_hours:
            raise ValueError(
                f"Se esperaban {self.horizon_hours} predicciones, "
                f"se recibieron {len(self.hourly_predictions)}"
            )

    @property
    def peak_predictions(self) -> list[HourlyPrice]:
        return [h for h in self.hourly_predictions if h.is_peak_hour]

    @property
    def avg_predicted_price(self) -> float:
        if not self.hourly_predictions:
            return 0.0
        return sum(h.predicted_cop for h in self.hourly_predictions) / len(self.hourly_predictions)

    @property
    def max_predicted_price(self) -> HourlyPrice:
        return max(self.hourly_predictions, key=lambda h: h.predicted_cop)

    @property
    def min_predicted_price(self) -> HourlyPrice:
        return min(self.hourly_predictions, key=lambda h: h.predicted_cop)

    @property
    def has_actuals(self) -> bool:
        return len(self.actuals) > 0
