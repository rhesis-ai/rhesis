"""
Base schema for all schemas

This module contains the base schema for all schemas in the application.
Note using Pydantic together with SQLAlchemy leads to a lot of code duplication.
This is a known issue and there are some workarounds. One of them is to use
helper libraries such as pydantic_sqlalchemy as future improvement.

"""

import datetime
from typing import Any, ClassVar, Optional

from pydantic import UUID4, BaseModel, ConfigDict, field_serializer, model_validator


def _organization_of(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("organization_id")
    return getattr(value, "organization_id", None)


class Base(BaseModel):
    """Shared base for read *and* write schemas, so it carries no server-owned identity.

    ``id`` and ``nano_id`` are assigned by the backend and must never be settable from a
    request body. Because every entity's ``<Entity>Base`` is inherited by both its
    ``Create``/``Update`` schemas and its response schemas, any field declared here leaks
    into write payloads. Read schemas therefore pick identity up from
    :class:`ServerIdentity` instead. Enforced by ``tests/backend/schemas/test_server_identity.py``.
    """

    project_id: Optional[UUID4] = None
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    # Set on user schemas so a parent can drop a nested user from another organization.
    is_user_schema: ClassVar[bool] = False

    @model_validator(mode="wrap")
    @classmethod
    def _drop_other_org_users(cls, data: Any, handler: Any) -> Any:
        # The user table has no RLS, so a stale cross-org user reference would load
        # and serialize that user's record. Never return it inside another org's row.
        # Only direct user fields are checked: no schema nests users in a list or dict.
        obj = handler(data)
        org = _organization_of(data) or _organization_of(obj)
        if org is None:
            return obj
        for name, value in obj.__dict__.items():
            if getattr(value, "is_user_schema", False):
                user_org = getattr(value, "organization_id", None)
                if user_org is not None and str(user_org) != str(org):
                    obj.__dict__[name] = None
        return obj

    @field_serializer("*")
    def serialize_datetime(self, value, _info):
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return value


class ServerIdentity(BaseModel):
    """Server-assigned identity, for response schemas only.

    Mix into a read schema to expose ``id``/``nano_id``. Never mix into a ``Create`` or
    ``Update`` schema: the backend owns both values. ``id`` stays optional here because
    response schemas that require it redeclare it as ``id: UUID4``.
    """

    id: Optional[UUID4] = None
    nano_id: Optional[str] = None
