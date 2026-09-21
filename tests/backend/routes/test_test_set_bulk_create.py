"""POST /test_sets/bulk says how many tests the set actually got.

The MCP ``count_check`` on ``create_test_set_bulk`` reads ``total_tests`` out
of this response to contradict an agent reporting the number it sent rather
than the number written (issue #2516). The field was absent for as long as
the check existed, so the check was a no-op on the one tool the issue was
about. These tests pin the field to the real size of the set.
"""

from fastapi import status
from fastapi.testclient import TestClient


def _payload(name: str, prompts: list[str]) -> dict:
    return {
        "name": name,
        "test_set_type": "Single-Turn",
        "tests": [
            {
                "prompt": {"content": content},
                "requirement": "Answers the question",
                "category": "Functional",
                "topic": "General",
            }
            for content in prompts
        ],
    }


class TestBulkCreateTestSetReportsItsSize:
    """The response has to carry the written count, not the requested one."""

    def test_the_response_counts_the_tests_created(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/test_sets/bulk", json=_payload("Counted set", ["one", "two", "three"])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total_tests"] == 3

    def test_the_two_counts_in_the_response_agree(self, authenticated_client: TestClient):
        """``attributes.metadata.total_tests`` has always been there, nested
        too deep for count_check to read. The top-level field is the same
        number, and has to stay the same number."""
        response = authenticated_client.post(
            "/test_sets/bulk", json=_payload("Agreeing set", ["one", "two", "three"])
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total_tests"] == body["attributes"]["metadata"]["total_tests"]

    def test_appending_reports_the_batch_not_the_new_total(self, authenticated_client: TestClient):
        """POST /tests/bulk is how a set larger than one call gets built, and
        the Architect sums the total_tests of each batch to know how big the
        set became. That sum is only right while this field means "written by
        this call". If it ever became "size of the set now", every batched set
        would be counted several times over and read as an overshoot.
        """
        created = authenticated_client.post(
            "/test_sets/bulk", json=_payload("Appended set", ["one", "two"])
        )
        assert created.status_code == status.HTTP_200_OK
        test_set_id = created.json()["id"]

        appended = authenticated_client.post(
            "/tests/bulk",
            json={
                "test_set_id": test_set_id,
                "tests": [
                    {
                        "prompt": {"content": content},
                        "requirement": "Answers the question",
                        "category": "Functional",
                        "topic": "General",
                    }
                    for content in ("three", "four", "five")
                ],
            },
        )

        assert appended.status_code == status.HTTP_200_OK
        assert appended.json()["total_tests"] == 3

        listed = authenticated_client.get(f"/test_sets/{test_set_id}/tests")
        assert len(listed.json()) == 5

    def test_the_count_matches_what_the_set_holds(self, authenticated_client: TestClient):
        """Reading the tests back must agree with the number the write claimed.

        A count taken from the request would still read 2 here; only one taken
        from the set itself stays right when those two numbers diverge.
        """
        created = authenticated_client.post(
            "/test_sets/bulk", json=_payload("Readback set", ["alpha", "beta"])
        )
        assert created.status_code == status.HTTP_200_OK
        claimed = created.json()["total_tests"]

        listed = authenticated_client.get(f"/test_sets/{created.json()['id']}/tests")
        assert listed.status_code == status.HTTP_200_OK
        assert claimed == len(listed.json())
