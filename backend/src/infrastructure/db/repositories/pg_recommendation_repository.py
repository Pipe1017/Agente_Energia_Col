from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.recommendation import HourlyOffer, Recommendation, RiskLevel
from ....domain.repositories.i_recommendation_repository import IRecommendationRepository
from ..models.recommendation_model import RecommendationModel

# Mapa de franjas horarias del LLM → hora representativa y etiqueta
_BUCKET_HOUR = {"off_peak": 3, "mid_peak": 12, "peak": 20}
_BUCKET_LABEL = {
    "off_peak": "Franja valle (00-06h)",
    "mid_peak": "Franja media (06-18h)",
    "peak": "Franja pico (18-23h)",
}


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

    @staticmethod
    def _parse_hourly_offers(raw) -> list[HourlyOffer]:
        """Convierte hourly_offers de la BD al formato de dominio.

        Soporta dos formatos:
        - Lista: [{"hour": "...", "suggested_price_cop": ..., "reasoning": "..."}]
        - Dict plano del LLM: {"off_peak": 210.0, "mid_peak": 240.0, "peak": 280.0}
        """
        if not raw:
            return []
        if isinstance(raw, list):
            return [
                HourlyOffer(
                    hour=datetime.fromisoformat(o["hour"]),
                    suggested_price_cop=o["suggested_price_cop"],
                    reasoning=o["reasoning"],
                )
                for o in raw
            ]
        # Dict plano: {"off_peak": 210.0, ...}
        today = date.today()
        result = []
        for bucket, price in raw.items():
            hour_num = _BUCKET_HOUR.get(bucket, 12)
            label = _BUCKET_LABEL.get(bucket, bucket)
            ts = datetime.combine(today, time(hour=hour_num), tzinfo=timezone.utc)
            result.append(HourlyOffer(
                hour=ts,
                suggested_price_cop=float(price),
                reasoning=label,
            ))
        return result

    def _to_domain(self, row: RecommendationModel) -> Recommendation:
        return Recommendation(
            id=row.id,
            agent_sic_code=row.agent_sic_code,
            generated_at=row.generated_at,
            prediction_id=row.prediction_id,
            narrative=row.narrative,
            hourly_offers=self._parse_hourly_offers(row.hourly_offers),
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
