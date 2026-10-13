"""OData filters on the shared ``apply_odata_filter`` layer.

odata_query types every literal it parses as a string, and psycopg 3 sends a bound
value with its declared type, so a UUID column compared with a literal reached
Postgres as ``uuid = varchar`` and failed.

odata_query also passed ``startswith``/``endswith``/``contains`` literals to LIKE
unescaped, so ``_`` and ``%`` in them acted as wildcards.
"""

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from rhesis.backend.app import models
from rhesis.backend.app.utils.odata import apply_odata_filter

OTHER = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def _compiled(filter_expr: str) -> str:
    query = apply_odata_filter(Query(models.Status), models.Status, filter_expr)
    return str(query.statement.compile(dialect=postgresql.psycopg.dialect()))


@pytest.mark.unit
@pytest.mark.parametrize(
    "filter_expr",
    [f"id eq {OTHER}", f"id eq '{OTHER}'", f"id ne '{OTHER}'", f"id in ('{OTHER}', '{OTHER}')"],
)
def test_a_uuid_literal_is_bound_as_uuid(filter_expr):
    sql = _compiled(filter_expr)
    assert "::UUID" in sql
    assert "::VARCHAR" not in sql


@pytest.mark.unit
def test_a_string_column_keeps_its_string_literal():
    assert "::VARCHAR" in _compiled("name eq 'Pass'")


@pytest.mark.integration
@pytest.mark.parametrize("quoted", [True, False])
def test_a_uuid_filter_runs_against_postgres(test_db, db_status, quoted):
    literal = f"'{db_status.id}'" if quoted else str(db_status.id)
    query = apply_odata_filter(test_db.query(models.Status), models.Status, f"id eq {literal}")

    assert [row.id for row in query.all()] == [db_status.id]


@pytest.mark.unit
def test_a_like_literal_is_escaped_inside_tolower():
    query = apply_odata_filter(
        Query(models.Status), models.Status, "contains(tolower(name),tolower('50%_/'))"
    )
    compiled = query.statement.compile(dialect=postgresql.psycopg.dialect())

    assert "ESCAPE '/'" in str(compiled)
    assert "50/%/_//" in compiled.params.values()


LIKE_NAMES = ["test_set.created", "testXset.created", "50% OFF", "500 off", "a/b", "a\\b"]


@pytest.fixture
def like_statuses(test_db, test_organization, test_type_lookup, db_user):
    for name in LIKE_NAMES:
        test_db.add(
            models.Status(
                name=name,
                entity_type_id=test_type_lookup.id,
                organization_id=test_organization.id,
                user_id=db_user.id,
            )
        )
    test_db.commit()


@pytest.mark.integration
@pytest.mark.parametrize(
    "filter_expr, expected",
    [
        ("startswith(name,'test_set.')", {"test_set.created"}),
        ("endswith(name,'t_set.created')", {"test_set.created"}),
        ("contains(name,'50%')", {"50% OFF"}),
        ("contains(tolower(name),tolower('50% off'))", {"50% OFF"}),
        ("startswith(toupper(name),toupper('test_'))", {"test_set.created"}),
        ("startswith(name,'a/')", {"a/b"}),
        ("endswith(name,'\\b')", {"a\\b"}),
    ],
)
def test_like_wildcards_in_a_literal_match_only_themselves(
    test_db, like_statuses, filter_expr, expected
):
    query = apply_odata_filter(test_db.query(models.Status), models.Status, filter_expr)

    assert {row.name for row in query.all()} & set(LIKE_NAMES) == expected
