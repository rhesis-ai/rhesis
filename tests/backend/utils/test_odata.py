"""OData filters against UUID columns.

odata_query types every literal it parses as a string, and psycopg 3 sends a bound
value with its declared type, so a UUID column compared with a literal reached
Postgres as ``uuid = varchar`` and failed.
"""

import uuid

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from rhesis.backend.app import models
from rhesis.backend.app.utils.odata import apply_odata_filter

OTHER = str(uuid.uuid4())


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
