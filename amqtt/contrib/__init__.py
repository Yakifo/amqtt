"""Module for plugins requiring additional dependencies."""

from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar

from sqlalchemy import JSON
from sqlalchemy import TypeDecorator

T = TypeVar("T")


class DataClassListJSON(TypeDecorator[list[dict[str, Any]]]):
    impl = JSON
    cache_ok = True

    def __init__(self, dataclass_type: type[T]) -> None:
        if not is_dataclass(dataclass_type):
            msg = f"{dataclass_type} must be a dataclass type"
            raise TypeError(msg)
        self.dataclass_type = dataclass_type
        super().__init__()

    def process_bind_param(
            self,
            value: list[Any] | None,  # Python -> DB
            dialect: Any
    ) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        return [asdict(item) for item in value]

    def process_result_value(
            self,
            value: list[dict[str, Any]] | None,  # DB -> Python
            dialect: Any
    ) -> list[Any] | None:
        if value is None:
            return None
        return [self.dataclass_type(**item) for item in value]
    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        # Required by SQLAlchemy, typically used for literal SQL rendering.
        return value
    @property
    def python_type(self) -> type:
        # Required by TypeEngine to indicate the expected Python type.
        return list
