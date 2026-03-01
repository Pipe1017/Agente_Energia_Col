from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.recommendation import HourlyOffer, Recommendation, RiskLevel
from ....domain.repositories.i_recommendation_repository import IRecommendationRepository
from ..models.recommendation_model import RecommendationModel


class PgRecommendationRepository(IRecommendationRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _offer_to_domain(data: dict) -> HourlyOffer:
        return HourlyOffer(
            hour=datetime.fromisoformat(data["hour"]),
            suggested_price_cop=data["suggested_price_cop"],
            reasoning=data["reasoning"],
        )

    @staticmethod
    def _offer_to_dict(o: HourlyOffer) -> dict:
        return {
            "hour": o.hour.isoformat(),
            "suggested_price_cop": o.suggested_price_cop,
            "reasoning": o.reasoning,
        }

    def _to_domain(self, row: RecommendationModel) -> Recommendation:
        return Recommendation(
            id=row.id,
            agent_sic_code=row.agent_sic_code,
            generated_at=row.generated_at,
            prediction_id=row.prediction_id,
            narrative=row.narrative,
            hourly_offers=[self._offer_to_domain(o) for o in row.hourly_offers],
            risk_level=RiskLevel(row.risk_level),
            key_factors=list(row.key_factors),
            llm_model_used=row.llm_model_used,
        )

    async def get_latest(self, agent_sic_code: str) -> Recommendation | None:
        result = await self._session.execute(
            select(RecommendationModel)
            .where(RecommendationModel.agent_sic_code == agent_sic_code.upper())
            .order_by(RecommendationModel.generated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        row = await self._session.get(RecommendationModel, recommendation_id)
        return self._to_domain(row) if row else None

    async def get_range(
        self,
        agent_sic_code: str,
        start: datetime,
        end: datetime,
    ) -> list[Recommendation]:
        result = await self._session.execute(
            select(RecommendationModel)
            .where(
                RecommendationModel.agent_sic_code == agent_sic_code.upper(),
                RecommendationModel.generated_at >= start,
                RecommendationModel.generated_at <= end,
            )
            .order_by(RecommendationModel.generated_at.desc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, recommendation: Recommendation) -> Recommendation:
        row = RecommendationModel(
            id=recommendation.id,
            agent_sic_code=recommendation.agent_sic_code,
            generated_at=recommendation.generated_at,
            prediction_id=recommendation.prediction_id,
            narrative=recommendation.narrative,
            hourly_offers=[self._offer_to_dict(o) for o in recommendation.hourly_offers],
            risk_level=recommendation.risk_level.value,
            key_factors=recommendation.key_factors,
            llm_model_used=recommendation.llm_model_used,
        )
        self._session.add(row)
        await self._session.flush()
        return recommendation
