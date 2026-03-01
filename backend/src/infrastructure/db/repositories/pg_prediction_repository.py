from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.prediction import HourlyPrice, PricePrediction
from ....domain.repositories.i_prediction_repository import IPredictionRepository
from ..models.prediction_model import PredictionModel


class PgPredictionRepository(IPredictionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _hourly_to_domain(data: dict) -> HourlyPrice:
        return HourlyPrice(
            target_hour=datetime.fromisoformat(data["target_hour"]),
            predicted_cop=data["predicted_cop"],
            lower_bound_cop=data["lower_bound_cop"],
            upper_bound_cop=data["upper_bound_cop"],
            confidence=data["confidence"],
        )

    @staticmethod
    def _hourly_to_dict(h: HourlyPrice) -> dict:
        return {
            "target_hour": h.target_hour.isoformat(),
            "predicted_cop": h.predicted_cop,
            "lower_bound_cop": h.lower_bound_cop,
            "upper_bound_cop": h.upper_bound_cop,
            "confidence": h.confidence,
        }

    def _to_domain(self, row: PredictionModel) -> PricePrediction:
        return PricePrediction(
            id=row.id,
            agent_sic_code=row.agent_sic_code,
            generated_at=row.generated_at,
            model_version_id=row.model_version_id,
            horizon_hours=row.horizon_hours,
            hourly_predictions=[self._hourly_to_domain(h) for h in row.hourly_predictions],
            actuals=[self._hourly_to_domain(h) for h in (row.actuals or [])],
            overall_confidence=row.overall_confidence,
        )

    async def get_latest(self, agent_sic_code: str) -> PricePrediction | None:
        result = await self._session.execute(
            select(PredictionModel)
            .where(PredictionModel.agent_sic_code == agent_sic_code.upper())
            .order_by(PredictionModel.generated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_id(self, prediction_id: UUID) -> PricePrediction | None:
        row = await self._session.get(PredictionModel, prediction_id)
        return self._to_domain(row) if row else None

    async def get_range(
        self,
        agent_sic_code: str,
        start: datetime,
        end: datetime,
    ) -> list[PricePrediction]:
        result = await self._session.execute(
            select(PredictionModel)
            .where(
                PredictionModel.agent_sic_code == agent_sic_code.upper(),
                PredictionModel.generated_at >= start,
                PredictionModel.generated_at <= end,
            )
            .order_by(PredictionModel.generated_at.desc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, prediction: PricePrediction) -> PricePrediction:
        row = PredictionModel(
            id=prediction.id,
            agent_sic_code=prediction.agent_sic_code,
            generated_at=prediction.generated_at,
            model_version_id=prediction.model_version_id,
            horizon_hours=prediction.horizon_hours,
            hourly_predictions=[self._hourly_to_dict(h) for h in prediction.hourly_predictions],
            actuals=[self._hourly_to_dict(h) for h in prediction.actuals],
            overall_confidence=prediction.overall_confidence,
        )
        self._session.add(row)
        await self._session.flush()
        return prediction

    async def update_actuals(self, prediction_id: UUID, actuals: list[HourlyPrice]) -> None:
        row = await self._session.get(PredictionModel, prediction_id)
        if not row:
            raise ValueError(f"Predicción no encontrada: {prediction_id}")
        row.actuals = [self._hourly_to_dict(h) for h in actuals]
        await self._session.flush()
