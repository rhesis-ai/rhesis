from typing import Any, Dict, List, Type, Union

from fastapi import HTTPException
from odata_query import ast
from odata_query import typing as odata_typing
from odata_query.grammar import ODataLexer, ODataParser
from odata_query.sqlalchemy import AstToSqlAlchemyOrmVisitor, functions_ext
from odata_query.sqlalchemy.shorthand import _get_joined_attrs
from sqlalchemy.orm import Query
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, ClauseElement
from sqlalchemy.sql.expression import literal
from sqlalchemy.types import NullType, String

_LIKE_ESCAPE = "/"
_CASE_FUNCTIONS = {"tolower": functions_ext.lower, "toupper": functions_ext.upper}


def apply_odata_filter(query: Query, model: Type, filter_expr: str | None) -> Query:
    """Apply OData filter to query if provided.

    The model parameter is unused here — the mapped class is inferred from
    the query object. The parameter is kept for API compatibility with
    callers that pass it alongside the query.
    """
    if filter_expr:
        try:
            query = _apply_odata_query(query, filter_expr)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing filter: {str(e)}") from e
        if query.whereclause is not None:
            _type_literals_as_their_columns(query.whereclause)
    return query


def _apply_odata_query(query: Query, filter_expr: str) -> Query:
    """``odata_query.sqlalchemy.apply_odata_query``, built on ``_OrmVisitor``."""
    model = query.__clause_element__().columns_clause_froms[0].entity_namespace
    transformer = _OrmVisitor(model)
    where_clause = transformer.visit(ODataParser().parse(ODataLexer().tokenize(filter_expr)))

    existing_joins = _get_joined_attrs(query)
    for relationship in transformer.join_relationships:
        if str(relationship) not in existing_joins and str(relationship.key) not in existing_joins:
            query = query.join(relationship)
    return query.filter(where_clause)


def _escape_like(text: str) -> str:
    """Escape ``text`` so a LIKE pattern with ``ESCAPE '/'`` matches it literally."""
    return (
        text.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )


class _OrmVisitor(AstToSqlAlchemyOrmVisitor):
    """odata_query's ORM visitor, with ``startswith``/``endswith``/``contains``
    matching their literal as plain text instead of as a LIKE pattern."""

    def _substr_function(self, field: ast._Node, substr: ast._Node, func: str) -> ClauseElement:
        odata_typing.typecheck(field, (ast.Identifier, ast.String), "field")
        odata_typing.typecheck(substr, ast.String, "substring")
        pattern = self._escaped_literal(substr)
        if pattern is None:
            return super()._substr_function(field, substr, func)
        return getattr(self.visit(field), func)(pattern, escape=_LIKE_ESCAPE)

    def _escaped_literal(self, node: ast._Node) -> ClauseElement | None:
        """The escaped pattern for a string literal, bare or in ``tolower``/``toupper``.

        None for anything else, such as a column, which can't be escaped here.
        """
        if isinstance(node, ast.String):
            return literal(_escape_like(node.py_val))
        case_function = isinstance(node, ast.Call) and _CASE_FUNCTIONS.get(node.func.name.lower())
        if not case_function or len(node.args) != 1:
            return None
        inner = self._escaped_literal(node.args[0])
        return None if inner is None else case_function(inner)


def _type_literals_as_their_columns(clause) -> None:
    """Give each string literal the type of the column it is compared with.

    odata_query types every literal it parses as a string, and psycopg 3 sends
    a bound value with its declared type, so ``test_id eq <uuid>`` would reach
    Postgres as ``uuid = varchar`` and fail.
    """

    def retype(binary: BinaryExpression) -> None:
        for side, other in ((binary.right, binary.left), (binary.left, binary.right)):
            if isinstance(other.type, NullType):
                continue
            for element in visitors.iterate(side):
                if isinstance(element, BindParameter) and isinstance(
                    element.type, (String, NullType)
                ):
                    element.type = other.type

    visitors.traverse(clause, {}, {"binary": retype})


def apply_select(
    data: Union[List[Dict[str, Any]], Dict[str, Any], Any],
    select: str | None,
) -> Union[List[Dict[str, Any]], Dict[str, Any], Any]:
    """Filter serialized response data to include only selected fields.

    Accepts a comma-separated list of field names (OData ``$select``).
    ``id`` is always included so that entities remain identifiable.

    Works on both single dicts and lists of dicts.  If *data* is a list
    of ORM/Pydantic objects, each item is converted via ``model_dump()``
    (Pydantic v2) or ``dict()`` first.
    """
    if not select:
        return data

    fields = {f.strip() for f in select.split(",") if f.strip()}
    fields.add("id")  # always include id

    def _pick(obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            d = obj
        elif hasattr(obj, "model_dump"):
            d = obj.model_dump()
        elif hasattr(obj, "dict"):
            d = obj.dict()
        else:
            # Exclude private/internal attributes (e.g. SQLAlchemy's _sa_instance_state)
            d = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return {k: v for k, v in d.items() if k in fields}

    if isinstance(data, list):
        return [_pick(item) for item in data]
    return _pick(data)


def combine_entity_type_filter(base_filter: str | None, entity_type: str | None) -> str | None:
    """
    Combines a base OData filter with an entity type filter.

    Args:
        base_filter: The existing OData filter expression, if any
        entity_type: The entity type value to filter by

    Returns:
        Combined OData filter expression or None if no filters
    """
    if not entity_type:
        return base_filter

    # Create entity type filter using OData navigation syntax
    # The Status model has an entity_type relationship to TypeLookup
    # We need to match both type_name='EntityType' and type_value=entity_type
    entity_type_filter = (
        f"entity_type/type_name eq 'EntityType' and entity_type/type_value eq '{entity_type}'"
    )

    # Combine with existing filter if present
    if base_filter:
        return f"({base_filter}) and ({entity_type_filter})"

    return entity_type_filter
