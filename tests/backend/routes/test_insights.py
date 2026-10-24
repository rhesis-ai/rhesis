"""Route tests for the generic Insights aggregation endpoints."""

import pytest
from fastapi import status

from rhesis.backend.app import models


@pytest.fixture
def two_test_results(
    test_db, test_organization, db_user, db_test_configuration, db_test_run, db_status
):
    """Two TestResult rows belonging to db_test_run."""
    results = []
    for _ in range(2):
        test = models.Test(
            priority=1,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(test)
        test_db.flush()

        result = models.TestResult(
            test_id=test.id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(result)
        results.append(result)

    test_db.commit()
    return db_test_run, results


@pytest.fixture
def one_run_and_one_unrun_test(
    test_db, test_organization, db_user, db_test_configuration, db_test_run, db_status
):
    """One test with a result, one test with none -- exercises v_test_stats."""
    run_test = models.Test(
        priority=1,
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    unrun_test = models.Test(
        priority=1,
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add_all([run_test, unrun_test])
    test_db.flush()

    test_db.add(
        models.TestResult(
            test_id=run_test.id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
    )
    test_db.commit()
    return run_test, unrun_test


@pytest.fixture
def timed_runs(test_db, test_organization, db_user, db_status, db_test_configuration):
    """Runs timed each way the platform records it, plus two that have no duration."""
    attributes = [
        {"total_execution_time_ms": 60000},
        {"started_at": "2026-10-01T10:00:00+00:00", "completed_at": "2026-10-01T10:02:00+00:00"},
        {"started_at": "2026-10-01T10:00:00+00:00"},  # still running
        # A plausible prefix that still fails the cast; it must not break the query.
        {"started_at": "2026-99-99T10:00:00+00:00", "completed_at": "2026-10-01T10:02:00+00:00"},
    ]
    runs = [
        models.TestRun(
            name=f"timed run {i}",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_configuration_id=db_test_configuration.id,
            attributes=attrs,
        )
        for i, attrs in enumerate(attributes)
    ]
    test_db.add_all(runs)
    test_db.commit()
    return runs


@pytest.mark.unit
class TestInsightsRoute:
    def test_group_by_and_measures_return_grouped_rows(
        self, authenticated_client, two_test_results
    ):
        db_test_run, _ = two_test_results

        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test_result",
                "measures": ["count"],
                "test_run_ids": [str(db_test_run.id)],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["entity"] == "test_result"
        assert body["dimensions"] == []
        assert body["rows"][0]["count"] == 2

    def test_pass_rate_is_computed(self, authenticated_client, two_test_results):
        """psycopg 3 binds the rate's 100.0 as float8, and Postgres has no
        round(double precision, int), so the rate must be rounded as numeric."""
        db_test_run, _ = two_test_results

        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test_result",
                "measures": ["count", "pass_rate"],
                "test_run_ids": [str(db_test_run.id)],
            },
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["rows"][0]["pass_rate"] == 0

    def test_test_entity_counts_unrun_tests(self, authenticated_client, one_run_and_one_unrun_test):
        run_test, unrun_test = one_run_and_one_unrun_test

        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test",
                "measures": ["count", "unrun_count"],
                "test_ids": [str(run_test.id), str(unrun_test.id)],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        row = response.json()["rows"][0]
        assert row["count"] == 2
        assert row["unrun_count"] == 1

    def test_group_by_test_run_returns_name_and_id(self, authenticated_client, two_test_results):
        """A bare UUID leaves callers (the Architect above all) unable to name the run,
        and a bare name can't be linked to -- so the dimension returns both."""
        db_test_run, _ = two_test_results

        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test_result",
                "group_by": ["test_run"],
                "measures": ["count"],
                "test_run_ids": [str(db_test_run.id)],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        row = response.json()["rows"][0]
        assert row["test_run"] == db_test_run.name
        assert row["test_run_id"] == str(db_test_run.id)

    def test_run_durations_come_from_run_timing(self, authenticated_client, timed_runs):
        """total_execution_time_ms first, else completed_at - started_at; untimed runs skipped."""
        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test_run",
                "measures": ["count", "avg_duration_ms", "p50_duration_ms", "max_duration_ms"],
                "test_run_ids": [str(run.id) for run in timed_runs],
            },
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        row = response.json()["rows"][0]
        assert row["count"] == 4
        assert row["avg_duration_ms"] == 90000
        assert row["p50_duration_ms"] == 90000
        assert row["max_duration_ms"] == 120000

    def test_schema_lists_run_duration_measures(self, authenticated_client):
        response = authenticated_client.get("/insights/schema")

        measures = response.json()["entities"]["test_run"]["measures"]
        assert measures["p95_duration_ms"]["kind"] == "duration"

    def test_unknown_entity_returns_400(self, authenticated_client):
        response = authenticated_client.get(
            "/insights/", params={"entity": "not_a_real_entity", "measures": ["count"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_group_by_returns_400(self, authenticated_client):
        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": "test_result",
                "group_by": ["not_a_real_dimension"],
                "measures": ["count"],
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_query_runs_named_subqueries(self, authenticated_client, two_test_results):
        db_test_run, _ = two_test_results
        run_id = str(db_test_run.id)

        response = authenticated_client.post(
            "/insights/query",
            json={
                "summary": {
                    "entity": "test_result",
                    "group_by": [],
                    "measures": ["count"],
                    "filters": {"test_run_ids": [run_id]},
                },
                "by_run": {
                    "entity": "test_result",
                    "group_by": ["test_run"],
                    "measures": ["count"],
                    "filters": {"test_run_ids": [run_id]},
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "queries" not in body
        assert "results" not in body
        assert body["summary"]["rows"][0]["count"] == 2
        assert body["by_run"]["entity"] == "test_result"

    def test_ids_returns_distinct_test_ids(self, authenticated_client, two_test_results):
        db_test_run, results = two_test_results
        expected = {str(r.test_id) for r in results}

        response = authenticated_client.get(
            "/insights/ids",
            params={
                "entity": "test_result",
                "test_run_ids": [str(db_test_run.id)],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["entity"] == "test_result"
        assert set(body["ids"]) == expected

    def test_ids_rejects_unknown_outcome(self, authenticated_client):
        response = authenticated_client.get(
            "/insights/ids",
            params={"entity": "test_result", "outcome": "maybe"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
