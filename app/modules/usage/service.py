from datetime import UTC, datetime
from uuid import UUID

from app.core.db import Database
from app.core.errors import NotFoundError
from app.modules.tenants.repository import TenantRepository
from app.modules.usage.repository import UsageRepository
from app.modules.usage.schemas import UsageSummary


def month_bounds(month: str | None, now: datetime) -> tuple[datetime, datetime]:
    """[start, end) of a calendar month in UTC; `month` is "YYYY-MM", default the current one."""
    year, number = (int(part) for part in month.split("-")) if month else (now.year, now.month)
    start = datetime(year, number, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if number == 12
        else datetime(year, number + 1, 1, tzinfo=UTC)
    )
    return start, end


class UsageService:
    def __init__(self, db: Database, usage: UsageRepository, tenants: TenantRepository) -> None:
        self._db = db
        self._usage = usage
        self._tenants = tenants

    async def summary(self, tenant_id: UUID, month: str | None = None) -> UsageSummary:
        start, end = month_bounds(month, datetime.now(UTC))
        async with self._db.transaction() as session:
            tenant = await self._tenants.get(session, tenant_id)
            if tenant is None:
                raise NotFoundError("Tenant")
            totals = await self._usage.totals(session, tenant_id, start, end)
        return UsageSummary(
            tenant_id=tenant_id,
            period_start=start,
            period_end=end,
            queries=totals.queries,
            input_tokens=totals.input_tokens,
            output_tokens=totals.output_tokens,
            estimated_cost_usd=totals.estimated_cost_usd,
            query_limit=tenant.monthly_query_limit,
            queries_remaining=max(0, tenant.monthly_query_limit - totals.queries),
        )
