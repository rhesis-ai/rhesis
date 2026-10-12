"""Every table has an audit decision, and every audited column a deliberate one.

Models are audited by default (``app/models/audit_policy.py``). These guards
fail when a new model or column would put customer content, a secret, or an
action name nobody chose into the audit log.
"""

import re

import pytest
from sqlalchemy import JSON, Text
from sqlalchemy.types import TypeDecorator

import rhesis.backend.ee.api_clients.clients  # maps auth_client
import rhesis.backend.ee.rbac.models  # noqa: F401  (maps role, role_permission, ...)
from rhesis.backend.app.models.audit_capture import audit_policy_of, plans
from rhesis.backend.app.models.audit_policy import AuditLink, AuditPolicy
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.utils.encryption import EncryptedString
from rhesis.backend.events.audit_actions import known_actions

# Names that usually hold a secret even when the column is not encrypted.
_SECRET_LOOKING = re.compile(r"password|secret|_hash$")


def _audited():
    for mapper in Base.registry.mappers:
        policy = audit_policy_of(mapper.class_)
        if isinstance(policy, AuditPolicy) and policy.audited:
            yield mapper.local_table, policy


def _declared(policy: AuditPolicy) -> set[str]:
    return set(policy.content) | set(policy.secret) | set(policy.plain) | set(policy.ignore)


def _is_text_or_json(column) -> bool:
    column_type = column.type
    if isinstance(column_type, EncryptedString):
        return False
    if isinstance(column_type, TypeDecorator):
        column_type = column_type.impl_instance
    return isinstance(column_type, (Text, JSON))


def test_text_and_json_columns_are_classified():
    """Free text and JSON is where customer content hides: decide each one."""
    unclassified = sorted(
        f"{table.name}.{column.name}"
        for table, policy in _audited()
        for column in table.columns
        if _is_text_or_json(column) and column.name not in _declared(policy)
    )
    assert not unclassified, (
        "Text/JSON columns on audited models must be listed as content, secret, plain or "
        f"ignore in the model's __audit__: {unclassified}"
    )


def test_secret_looking_columns_are_declared():
    undeclared = sorted(
        f"{table.name}.{column.name}"
        for table, policy in _audited()
        for column in table.columns
        if _SECRET_LOOKING.search(column.name)
        and not isinstance(column.type, EncryptedString)
        and column.name not in _declared(policy)
    )
    assert not undeclared, f"Declare these as secret (or plain if they are not): {undeclared}"


def test_declared_columns_exist():
    typos = sorted(
        f"{table.name}.{name}"
        for table, policy in _audited()
        for name in _declared(policy) | {policy.org_column}
        if name not in table.c
    )
    assert not typos, f"__audit__ names columns that do not exist: {typos}"


def test_every_unmapped_table_declares_its_link():
    mapped = {mapper.local_table.name for mapper in Base.registry.mappers}
    undeclared = sorted(
        table.name
        for table in Base.metadata.tables.values()
        if table.name not in mapped and not isinstance(table.info.get("audit"), AuditLink)
    )
    assert not undeclared, (
        "Link tables need info={'audit': AuditLink(...)} so their writes are recorded: "
        f"{undeclared}"
    )


@pytest.fixture
def catalog() -> list[str]:
    from rhesis.backend.app.auth.capabilities import get_all_capabilities, register_capabilities
    from rhesis.backend.app.main import app

    register_capabilities(app)
    return get_all_capabilities()


def test_every_action_the_hooks_can_produce_is_known(catalog):
    produced = set()
    for plan in plans().by_table.values():
        if isinstance(plan, AuditLink):
            if plan.owner is not None:
                produced.add(f"{plan.owner}.updated")
        else:
            produced |= {f"{plan.resource}.{past}" for past in ("created", "updated", "deleted")}
    unknown = sorted(produced - known_actions(catalog))
    assert not unknown, (
        "Row changes would be recorded under actions the capability catalog does not have. "
        f"Set AuditPolicy(resource=...) to the capability resource: {unknown}"
    )
