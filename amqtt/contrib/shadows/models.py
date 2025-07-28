import time
from typing import Any, Optional
import uuid

from sqlalchemy import JSON, CheckConstraint, Integer, String, UniqueConstraint, desc, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, Session, mapped_column

from amqtt.contrib.shadows.states import StateDocument


class Base(DeclarativeBase):
    pass


class Shadow(Base):
    __tablename__ = "shadows_shadow"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] =mapped_column(Integer, nullable=False)

    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        UniqueConstraint("device_id", "name", "version", name="uq_device_id_name_version"),
    )

    @classmethod
    async def latest_version(cls, session: AsyncSession, device_id: str, name: str) -> Optional["Shadow"]:
        stmt = (
            select(cls).where(
                cls.device_id == device_id,
                cls.name == name
            ).order_by(desc(cls.version)).limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


@event.listens_for(Shadow, "before_insert")
def assign_incremental_version(_: Mapper[Any], connection: Session, target: "Shadow") -> None:
    """Get the latest version of the state document."""
    stmt = (
        select(func.max(Shadow.version))
        .where(
            Shadow.device_id == target.device_id,
            Shadow.name == target.name
        )
    )
    result = connection.execute(stmt).scalar_one_or_none()
    target.version = (result or 0) + 1


@event.listens_for(Shadow, "before_insert")
def convert_state_document_to_json(_1: Mapper[Any], _2: Session, target: "Shadow") -> None:
    """Listen for insertion and convert state document to json."""
    if not isinstance(target.state, StateDocument):
        msg = "'state' field needs to be a StateDocument"
        raise TypeError(msg)

    target.state = target.state.to_dict()
