"""Both bulk routes store every field a test carries, and /tests/bulk says what it created.

Endpoint request templates read `test_parameters`, so a test created without them runs with
blank values. Before this, /test_sets/bulk dropped `test_parameters` and /tests/bulk dropped
the test's metadata, both silently, and /tests/bulk returned no ids to find the tests by.
"""

from fastapi import status
from fastapi.testclient import TestClient

PARAMETERS = {"account": "A-17", "region": "eu"}
METADATA = {"source": "import", "case": 3}


def _test(content: str) -> dict:
    return {
        "prompt": {"content": content},
        "requirement": "Answers the question",
        "category": "Functional",
        "topic": "General",
        "test_parameters": PARAMETERS,
        "metadata": METADATA,
    }


class TestTestSetBulkKeepsFields:
    def test_parameters_and_metadata_are_stored(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/test_sets/bulk",
            json={"name": "Kept fields", "test_set_type": "Single-Turn", "tests": [_test("q1")]},
        )
        assert response.status_code == status.HTTP_200_OK

        tests = authenticated_client.get(f"/test_sets/{response.json()['id']}/tests").json()
        assert [t["test_parameters"] for t in tests] == [PARAMETERS]
        assert [t["test_metadata"] for t in tests] == [METADATA]


class TestTestsBulkKeepsFields:
    def test_it_returns_the_ids_it_created(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/tests/bulk", json={"tests": [_test("a"), _test("b")]}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["total_tests"] == 2
        assert len(body["test_ids"]) == 2
        contents = {
            authenticated_client.get(f"/tests/{test_id}").json()["prompt"]["content"]
            for test_id in body["test_ids"]
        }
        assert contents == {"a", "b"}

    def test_parameters_and_metadata_are_stored(self, authenticated_client: TestClient):
        response = authenticated_client.post("/tests/bulk", json={"tests": [_test("kept")]})
        assert response.status_code == status.HTTP_200_OK

        stored = authenticated_client.get(f"/tests/{response.json()['test_ids'][0]}").json()
        assert stored["test_parameters"] == PARAMETERS
        assert stored["test_metadata"] == METADATA
