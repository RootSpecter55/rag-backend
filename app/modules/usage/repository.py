from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.queries.models import Query


@dataclass(frozen=True)
class UsageTotals:
    queries: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal


class UsageRepository:
    """Usage has no table of its own: it is aggregated from the queries table."""

    async def totals(
        self, session: AsyncSession, tenant_id: UUID, start: datetime, end: datetime
    ) -> UsageTotals:
        row = (
            await session.execute(
                select(
                    func.count(Query.id),
                    func.coalesce(func.sum(Query.input_tokens), 0),
                    func.coalesce(func.sum(Query.output_tokens), 0),
                    func.coalesce(func.sum(Query.estimated_cost_usd), 0),
                ).where(
                    Query.tenant_id == tenant_id,
                    Query.created_at >= start,
                    Query.created_at < end,
                )
            )
        ).one()
        return UsageTotals(int(row[0]), int(row[1]), int(row[2]), Decimal(row[3]))
