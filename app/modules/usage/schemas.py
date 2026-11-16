from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.schemas import ApiModel


class UsageSummary(ApiModel):
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    queries: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    query_limit: int
    queries_remaining: int
