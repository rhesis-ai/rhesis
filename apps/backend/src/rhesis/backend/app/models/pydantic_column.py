"""SQLAlchemy ``TypeDecorator``s that bridge JSONB columns to Pydantic models.

Two helpers, intentionally kept small:

- :func:`pydantic_jsonb_column` wraps a single Pydantic model: the JSON
  shape on disk is the model's ``model_dump`` output and reads return a
  validated instance.
- :func:`pydantic_list_jsonb_column` wraps a homogeneous list of one
  Pydantic model. Disk shape is a JSON array (``[...]``), not a wrapped
  ``{"items": [...]}`` envelope, so SQL queries like
  ``jsonb_array_length(versions)`` keep working.

Both decorators are tolerant on read: raw ``dict`` / ``list`` payloads
are accepted alongside already-typed Pydantic instances. This matters
because Alembic migrations write JSON literals (``DEFAULT '{"fields":
[]}'``) and SQLAlchemy may surface them as plain Python objects on
first read before any ``model_validate`` round-trip happens.
"""

from typing import Any, List, Type, TypeVar

from pydantic import BaseModel, TypeAdapter
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

T = TypeVar("T", bound=BaseModel)


class PydanticColumn(TypeDecorator):
    """Map a JSONB column to a single Pydantic model on read/write."""

    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_type: Type[T], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pydantic_type = pydantic_type

    def process_bind_param(self, value: T | dict | None, dialect: Any) -> dict | None:
        if value is None:
            return None
        if isinstance(value, self.pydantic_type):
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        return value

    def process_result_value(self, value: dict | str | None, dialect: Any) -> T | None:
        if value is None:
            return None
        if isinstance(value, str):
            import json

            value = json.loads(value)
        return self.pydantic_type.model_validate(value)


class PydanticListColumn(TypeDecorator):
    """Map a JSONB array column to ``list[T]`` of one Pydantic model.

    Stores as a JSON array (``[...]``), preserving the natural shape
    described in the schema (``versions JSONB NOT NULL DEFAULT '[]'``)
    so SQL like ``jsonb_array_length(versions)`` works without an
    envelope key.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_type: Type[T], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pydantic_type = pydantic_type
        self._adapter: TypeAdapter[list[T]] = TypeAdapter(list[pydantic_type])

    def process_bind_param(self, value: List[T] | List[dict] | None, dialect: Any) -> list | None:
        if value is None:
            return None
        out: list = []
        for item in value:
            if isinstance(item, self.pydantic_type):
                out.append(item.model_dump(mode="json", by_alias=True, exclude_none=True))
            else:
                out.append(item)
        return out

    def process_result_value(self, value: list | str | None, dialect: Any) -> List[T] | None:
        if value is None:
            return None
        if isinstance(value, str):
            import json

            value = json.loads(value)
        return self._adapter.validate_python(value)


def pydantic_jsonb_column(pydantic_type: Type[T], **kwargs) -> Any:
    """Helper factory for :class:`PydanticColumn`."""
    return PydanticColumn(pydantic_type, **kwargs)


def pydantic_list_jsonb_column(pydantic_type: Type[T], **kwargs) -> Any:
    """Helper factory for :class:`PydanticListColumn`."""
    return PydanticListColumn(pydantic_type, **kwargs)
