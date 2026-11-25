"""``$select`` applied to the serialized response of routes that declare it."""

from typing import Optional

import pytest
from fastapi import FastAPI, Query, Response
from fastapi.testclient import TestClient
from pydantic import BaseModel

from rhesis.backend.app.utils.select_projection import apply_select, apply_select_projection

pytestmark = pytest.mark.unit


class Item(BaseModel):
    id: str
    name: str
    note: Optional[str] = None


class Row:
    """Stands in for an ORM row: carries an attribute the response model does not list."""

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.note = "n"
        self.internal = "kept-out"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.get("/items", response_model=list[Item])
    def list_items(
        response: Response,
        select: Optional[str] = Query(None, alias="$select"),
    ):
        response.headers["X-Total-Count"] = "2"
        return [Row("1", "a"), Row("2", "b")]

    @app.get("/plain", response_model=list[Item])
    def list_plain():
        return [Row("1", "a")]

    apply_select_projection(app)
    return TestClient(app)


class TestApplySelect:
    def test_keeps_selected_fields_and_id(self):
        data = [{"id": 1, "name": "a", "note": "x"}]
        assert apply_select(data, "name") == [{"id": 1, "name": "a"}]

    def test_single_object(self):
        assert apply_select({"id": 1, "name": "a", "note": "x"}, "note") == {"id": 1, "note": "x"}

    def test_no_select_returns_data_unchanged(self):
        data = [{"id": 1, "name": "a"}]
        assert apply_select(data, None) is data

    def test_non_dict_items_pass_through(self):
        assert apply_select(["a", 1], "name") == ["a", 1]


class TestSelectProjection:
    def test_select_narrows_the_response(self, client):
        response = client.get("/items", params={"$select": "name"})
        assert response.status_code == 200
        assert response.json() == [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]

    def test_select_returns_only_schema_fields(self, client):
        response = client.get("/items", params={"$select": "name,internal"})
        assert response.json() == [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]

    def test_without_select_returns_the_full_schema(self, client):
        response = client.get("/items")
        assert response.json()[0] == {"id": "1", "name": "a", "note": "n"}

    def test_keeps_headers_set_by_the_route(self, client):
        response = client.get("/items", params={"$select": "name"})
        assert response.headers["X-Total-Count"] == "2"
        assert int(response.headers["content-length"]) == len(response.content)

    def test_routes_without_select_ignore_it(self, client):
        response = client.get("/plain", params={"$select": "name"})
        assert response.json() == [{"id": "1", "name": "a", "note": "n"}]
