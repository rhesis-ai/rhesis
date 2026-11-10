"""Which model attributes a client may filter or sort on.

Two rules, both derived from the models so a new column is covered without a
list to update:

- Secret columns are never queryable: ``EncryptedString`` columns, columns the
  model's ``__audit__`` policy marks ``secret``, and credential-named columns.
- The ``user``, ``token`` and ``refresh_token`` tables sit outside row-level
  security, so a relationship into them can reach rows of other organizations.
  Through a relationship only the display fields below are queryable.
"""

import re
from functools import lru_cache

from sqlalchemy import inspect

from rhesis.backend.app.utils.encryption import EncryptedString

# Backstop for secrets that are neither encrypted nor in an audit policy,
# such as refresh_token.token_hash on an unaudited model.
_SECRET_NAME_PATTERN = re.compile(r"password|secret|credential|api_key|token_hash")

# Table name -> attributes queryable when the table is reached through a relationship.
_RELATED_SAFE_FIELDS: dict[str, frozenset[str]] = {
    "user": frozenset({"id", "name", "email", "given_name", "family_name"}),
    "token": frozenset({"id"}),
    "refresh_token": frozenset({"id"}),
}


@lru_cache(maxsize=None)
def secret_column_keys(model: type) -> frozenset[str]:
    """Attribute keys of *model* that hold secrets."""
    declared = set(getattr(getattr(model, "__audit__", None), "secret", ()))
    return frozenset(
        prop.key
        for prop in inspect(model).column_attrs
        for column in prop.columns[:1]
        if isinstance(column.type, EncryptedString)
        or column.name in declared
        or _SECRET_NAME_PATTERN.search(column.name)
    )


def queryable_field_error(model: type, name: str, via_relationship: bool) -> str | None:
    """Why *name* on *model* cannot be filtered or sorted on, or None if it can.

    ``via_relationship`` is True when *model* was reached by navigating from
    another model rather than being the endpoint's own model.
    """
    if name not in inspect(model).all_orm_descriptors.keys():
        return f"Unknown field '{name}'"
    if name in secret_column_keys(model):
        return f"Field '{name}' cannot be used in filters or sorting"
    if via_relationship and not _is_related_safe(model, name):
        return f"Field '{name}' cannot be used through a relationship"
    return None


def sortable_field_error(model: type, name: str) -> str | None:
    """Why *name* cannot be a ``sort_by`` column of *model*, or None if it can."""
    error = queryable_field_error(model, name, via_relationship=False)
    if error:
        return error
    relationship = inspect(model).relationships.get(name)
    # Ordering by a relationship joins its table in; none of these fields are safe there.
    if relationship is not None and relationship.mapper.local_table.name in _RELATED_SAFE_FIELDS:
        return f"Field '{name}' cannot be used for sorting"
    return None


def _is_related_safe(model: type, name: str) -> bool:
    safe = _RELATED_SAFE_FIELDS.get(inspect(model).local_table.name)
    return safe is None or name in safe
