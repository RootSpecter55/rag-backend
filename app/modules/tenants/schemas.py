from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import ApiModel


class TenantCreate(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    monthly_query_limit: int | None = Field(default=None, ge=0)


class TenantUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    monthly_query_limit: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def not_empty(self) -> "TenantUpdate":
        if self.name is None and self.monthly_query_limit is None:
            raise ValueError("Provide at least one field to update")
        return self


class TenantOut(ApiModel):
    id: UUID
    name: str
    monthly_query_limit: int
    created_at: datetime


class TenantWithKey(ApiModel):
    tenant: TenantOut
    api_key: str = Field(description="Shown only once; store it now.")
