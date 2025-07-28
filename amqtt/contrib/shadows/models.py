from collections.abc import Sequence
from dataclasses import asdict
import logging
import time
from typing import Any, Optional
import uuid

from sqlalchemy import JSON, CheckConstraint, Integer, String, UniqueConstraint, desc, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, Session, make_transient, mapped_column

from amqtt.contrib.shadows.states import StateDocument

logger = logging.getLogger(__name__)


class ShadowUpdateError(Exception):
    def __init__(self, message: str = "updating an existing Shadow is not allowed") -> None:
        super().__init__(message)


class Base(DeclarativeBase):
    pass


def default_state_document() -> dict[str, Any]:
    """Create a default (empty) state document, factory for model field."""
    return asdict(StateDocument())


class Shadow(Base):
    __tablename__ = "shadows_shadow"

    id: Mapped[str] | None = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] =mapped_column(Integer, nullable=False)

    _state: Mapped[dict[str, Any]] = mapped_column("state", JSON, nullable=False, default=dict)

    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    __table_args__ = (
        CheckConstraint("version > 0", name="check_quantity_positive"),
        UniqueConstraint("device_id", "name", "version", name="uq_device_id_name_version"),
    )

    @property
    def state(self) -> StateDocument:
        return StateDocument.from_dict(self._state)

    @state.setter
    def state(self, value: StateDocument) -> None:
        self._state = asdict(value)

    @classmethod
    async def latest_version(cls, session: AsyncSession, device_id: str, name: str) -> Optional["Shadow"]:
        """Get the latest version of the shadow associated with the device and name."""
        stmt = (
            select(cls).where(
                cls.device_id == device_id,
                cls.name == name
            ).order_by(desc(cls.version)).limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def all(cls, session: AsyncSession, device_id: str, name: str) -> Sequence["Shadow"]:
        """Return a list of all shadows associated with the device and name."""
        stmt = (
                select(cls).where(
                    cls.device_id == device_id,
                    cls.name == name
                ).order_by(desc(cls.version)))
        result = await session.execute(stmt)
        return result.scalars().all()


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


@event.listens_for(Shadow, "before_update")
def prevent_update(_mapper: Mapper[Any], _session: Session, _instance: "Shadow") -> None:
    """Prevent existing shadow from being updated."""
    raise ShadowUpdateError


@event.listens_for(Session, "before_flush")
def convert_update_to_insert(session: Session, _flush_context: object, _instances:object | None) -> None:
    """Force a shadow to insert a new version, instead of updating an existing."""
    # Make a copy of the dirty set so we can safely mutate the session
    dirty = list(session.dirty)

    for obj in dirty:
        if not session.is_modified(obj, include_collections=False):
            continue  # skip unchanged

        # You can scope this to a particular class
        if not isinstance(obj, Shadow):
            continue

        # Clone logic: convert update into insert
        session.expunge(obj)         # remove from session
        make_transient(obj)          # remove identity and history
        obj.id = ""                  # clear primary key
        obj.version += 1             # bump version or modify fields

        session.add(obj)             # re-add as new object

_listener_example = '''#
# @event.listens_for(Shadow, "before_insert")
# def convert_state_document_to_json(_1: Mapper[Any], _2: Session, target: "Shadow") -> None:
#     """Listen for insertion and convert state document to json."""
#     if not isinstance(target.state, StateDocument):
#         msg = "'state' field needs to be a StateDocument"
#         raise TypeError(msg)
#
#     target.state = target.state.to_dict()
'''
