"""OData ``$filter`` and ``sort_by`` may only reach columns that are safe to query.

A filter or sort on a secret column is a value oracle even when the column is
never returned: ``startswith(password_hash,'$2b$12$a')`` answers yes/no per row
and ``sort_by=password_hash`` orders rows by the hash. The ``user``, ``token``
and ``refresh_token`` tables sit outside row-level security, so navigating into
them from another entity is limited to display fields.
"""

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from rhesis.backend.app import models
from rhesis.backend.app.utils.odata import apply_odata_filter
from rhesis.backend.app.utils.query_validation import validate_sort_field

pytestmark = pytest.mark.security


# --- Rejected through the real routes ----------------------------------------

REJECTED_FILTERS = [
    ("/users/", "startswith(password_hash,'$2b$')"),
    ("/users/", "password_hash ne null"),
    ("/users/", "refresh_tokens/any(t: startswith(t/token_hash,'a'))"),
    ("/users/", "tokens/any(t: startswith(t/token_hash,'a'))"),
    ("/users/", "tokens/any(t: t/name eq 'a')"),
    ("/test_sets/", "startswith(user/password_hash,'$2b$')"),
    ("/tests/", "startswith(assignee/password_hash,'$2b$')"),
    ("/tests/", "startswith(owner/password_hash,'$2b$')"),
    ("/test_runs/", "startswith(user/password_hash,'$2b$')"),
    ("/test_sets/", "startswith(user/external_provider_id,'a')"),
    ("/test_sets/", "user/organization/name eq 'a'"),
    ("/tokens/", "startswith(token_hash,'a')"),
    ("/tokens/", "startswith(token,'a')"),
    ("/tokens/", "startswith(user/password_hash,'$2b$')"),
    ("/models/", "startswith(key,'sk-')"),
    ("/endpoints/", "startswith(auth_token,'a')"),
    ("/endpoints/", "client_secret ne null"),
    ("/tests/", "startswith(soft_delete,'a')"),
    ("/tasks/", "startswith(assignee/password_hash,'$2b$')"),
]


@pytest.mark.parametrize("path,filter_expr", REJECTED_FILTERS)
def test_filter_on_restricted_field_is_rejected(authenticated_client, path, filter_expr):
    response = authenticated_client.get(path, params={"$filter": filter_expr})

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert "filter" in response.json()["detail"].lower()


REJECTED_SORTS = [
    ("/users/", "password_hash"),
    ("/tokens/", "token_hash"),
    ("/tokens/", "token"),
    ("/models/", "key"),
    ("/endpoints/", "auth_token"),
]


@pytest.mark.parametrize("path,sort_by", REJECTED_SORTS)
def test_sort_on_secret_field_is_rejected(authenticated_client, path, sort_by):
    response = authenticated_client.get(path, params={"sort_by": sort_by})

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert sort_by in response.json()["detail"]


def test_sort_error_does_not_list_secret_columns(authenticated_client):
    response = authenticated_client.get("/users/", params={"sort_by": "nope"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.json()["detail"]
    assert "password_hash" not in response.json()["detail"]


# --- Filters and sorts the frontend sends still work -------------------------

ALLOWED_FILTERS = [
    # Team page
    (
        "/users/",
        "(contains(email,'a') or contains(name,'a') or contains(given_name,'a') "
        "or contains(family_name,'a'))",
    ),
    ("/users/", "is_active eq true and joined_at ne null"),
    # Tokens page
    (
        "/tokens/",
        "contains(tolower(name),tolower('a')) or contains(tolower(token_obfuscated),tolower('a'))",
    ),
    ("/tokens/", "expires_at eq null and last_used_at ne null"),
    # Test sets, test runs, knowledge: executor / owner name
    ("/test_sets/", "contains(tolower(user/name),tolower('alice'))"),
    ("/test_runs/", "contains(tolower(user/name),tolower('alice'))"),
    ("/sources/", "contains(tolower(user/name),tolower('alice'))"),
    # User display fields through each relationship into user
    *[
        (
            "/tests/",
            " or ".join(
                f"contains(tolower({rel}/{field}), tolower('a'))"
                for field in ("name", "email", "given_name", "family_name")
            ),
        )
        for rel in ("assignee", "owner", "user")
    ],
    (
        "/tests/",
        "contains(tolower(topic/name), tolower('a')) or "
        "contains(tolower(prompt/content), tolower('a'))",
    ),
    ("/tests/", "_tags_relationship/any(t: tolower(t/tag/name) eq tolower('a'))"),
    ("/tests/", "assignee/id eq 3fa85f64-5717-4562-b3fc-2c963f66afa6"),
    ("/tests/", "assignee_id eq 3fa85f64-5717-4562-b3fc-2c963f66afa6"),
    ("/tasks/", "tolower(assignee/name) eq tolower('alice')"),
    ("/models/", "contains(tolower(name),tolower('gpt'))"),
    ("/endpoints/", "contains(tolower(name),tolower('a'))"),
]


@pytest.mark.parametrize("path,filter_expr", ALLOWED_FILTERS)
def test_frontend_filters_still_work(authenticated_client, path, filter_expr):
    response = authenticated_client.get(path, params={"$filter": filter_expr})

    assert response.status_code == status.HTTP_200_OK, response.text


ALLOWED_SORTS = [
    ("/users/", "email"),
    ("/users/", "name"),
    ("/tokens/", "name"),
    ("/tokens/", "created_at"),
    ("/models/", "name"),
    ("/tests/", "content"),
]


@pytest.mark.parametrize("path,sort_by", ALLOWED_SORTS)
def test_frontend_sorts_still_work(authenticated_client, path, sort_by):
    response = authenticated_client.get(path, params={"sort_by": sort_by})

    assert response.status_code == status.HTTP_200_OK, response.text


# --- The rule itself ---------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,filter_expr",
    [
        (models.Tool, "startswith(credentials,'a')"),
        (models.Organization, "startswith(rhesis_api_key,'a')"),
        (models.Organization, "sso_config ne null"),
        (models.Endpoint, "last_token ne null"),
        (models.RefreshToken, "startswith(token_hash,'a')"),
        (models.RefreshToken, "startswith(user/password_hash,'a')"),
        (models.Test, "startswith(organization/rhesis_api_key,'a')"),
    ],
)
def test_secret_columns_are_rejected_on_every_model(model, filter_expr):
    with pytest.raises(HTTPException) as exc:
        apply_odata_filter(Query(model), model, filter_expr)

    assert exc.value.status_code == 400


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,sort_by",
    [
        (models.Tool, "credentials"),
        (models.User, "tokens"),
        (models.Test, "assignee"),
        (models.Test, "soft_delete"),
    ],
)
def test_sort_rejects_secrets_and_relationships(model, sort_by):
    with pytest.raises(HTTPException) as exc:
        validate_sort_field(model, sort_by)

    assert exc.value.status_code == 400
