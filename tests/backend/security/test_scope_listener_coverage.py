"""The ORM tenant filter covers every org-scoped model, including the EE ones.

EE models are mapped after the scope listeners register, so a filter set built once at
registration missed them and left those tables to RLS alone.
"""

import uuid

import pytest
from sqlalchemy import event, select

import rhesis.backend.app.main  # noqa: F401  (maps the EE models, as at runtime)
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.scope_events import EXEMPT_TABLES
from rhesis.backend.app.scope import RequestScope, bind_scope, bypass_tenant_filter, reset_scope
from rhesis.backend.app.utils.query_utils import has_organization_id
from rhesis.backend.ee.audit.streaming import crud as destination_crud
from rhesis.backend.ee.audit.streaming.models import AuditDestination
from rhesis.backend.ee.rbac.models import Role
from tests.backend.fixtures.rls import as_org

EE_TABLES = {"audit_destination", "auth_client", "organization_member", "role"}


def _tenant_models():
    models = {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
        if has_organization_id(mapper.class_) and mapper.class_.__tablename__ not in EXEMPT_TABLES
    }
    return [models[name] for name in sorted(models)]


def _emitted_sql(db, stmt, organization_id) -> str:
    statements = []
    conn = db.connection()

    def capture(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(conn, "before_cursor_execute", capture)
    token = bind_scope(RequestScope(organization_id=str(organization_id)))
    try:
        db.execute(stmt).all()
    finally:
        reset_scope(token)
        event.remove(conn, "before_cursor_execute", capture)
    return "\n".join(statements)


@pytest.mark.security
def test_ee_models_are_in_the_checked_set():
    assert EE_TABLES <= {m.__tablename__ for m in _tenant_models()}


@pytest.mark.security
@pytest.mark.parametrize("model", _tenant_models(), ids=lambda m: m.__tablename__)
def test_select_carries_org_predicate(test_db, test_org_id, model):
    sql = _emitted_sql(test_db, select(model.organization_id).limit(1), test_org_id)

    where = sql.partition("WHERE")[2]
    assert f"{model.__tablename__}.organization_id" in where, sql


@pytest.mark.security
def test_built_in_roles_stay_visible_and_foreign_roles_do_not(test_db, test_org_id):
    foreign_org = uuid.uuid4()
    with bypass_tenant_filter():
        test_db.execute(
            Base.metadata.tables["organization"]
            .insert()
            .values(id=foreign_org, name=f"Foreign {foreign_org.hex[:8]}", is_active=True)
        )
    with as_org(test_db, foreign_org):
        foreign_role = Role(
            name="Foreign custom", display_name="x", organization_id=foreign_org, scope="project"
        )
        test_db.add(foreign_role)
        test_db.flush()
        foreign_role_id = foreign_role.id

    token = bind_scope(RequestScope(organization_id=test_org_id))
    try:
        ids = {r.id for r in test_db.execute(select(Role)).scalars()}
        names = {r.name for r in test_db.execute(select(Role)).scalars() if r.is_built_in}
    finally:
        reset_scope(token)

    assert foreign_role_id not in ids
    assert {"Owner", "Admin", "Member"} <= names


@pytest.mark.security
def test_destination_lookup_filters_on_org_without_rls(admin_test_db, test_org_id):
    """Run as the superuser so only the explicit predicate stands between the orgs."""
    db = admin_test_db
    foreign_org = uuid.uuid4()
    db.execute(
        Base.metadata.tables["organization"]
        .insert()
        .values(id=foreign_org, name=f"Foreign {foreign_org.hex[:8]}", is_active=True)
    )
    destination = AuditDestination(
        organization_id=foreign_org,
        name="foreign sink",
        kind="webhook",
        config="{}",
        cursor_recorded_at=destination_crud.transaction_start(db),
        cursor_id=uuid.UUID(int=0),
    )
    db.add(destination)
    db.flush()

    with bypass_tenant_filter():
        found = destination_crud.get_destination(db, destination.id, uuid.UUID(test_org_id))
        listed = destination_crud.list_destinations(db, uuid.UUID(test_org_id))

    assert found is None
    assert destination.id not in {d.id for d in listed}
