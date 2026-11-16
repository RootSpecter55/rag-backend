from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.db import Base


class BaseRepository[ModelT: Base]:
    """Repository pattern: generic data access shared by every module.

    Services never build queries; they call these methods with a session.
    """

    model: ClassVar[type[Any]]

    async def get(self, session: AsyncSession, id_: UUID) -> ModelT | None:
        return await session.get(self.model, id_)

    async def add(self, session: AsyncSession, obj: ModelT) -> ModelT:
        session.add(obj)
        await session.flush()  # assigns defaults (id, created_at) without committing
        await session.refresh(obj)
        return obj

    async def delete(self, session: AsyncSession, obj: ModelT) -> None:
        await session.delete(obj)
        await session.flush()

    async def list(
        self,
        session: AsyncSession,
        *where: ColumnElement[bool],
        order_by: InstrumentedAttribute[Any] | ColumnElement[Any],
        offset: int,
        limit: int,
    ) -> tuple[list[ModelT], int]:
        """One page of rows matching `where`, plus the total count."""
        rows = await session.scalars(
            select(self.model).where(*where).order_by(order_by).offset(offset).limit(limit)
        )
        total = await session.scalar(select(func.count()).select_from(self.model).where(*where))
        return list(rows), total or 0
