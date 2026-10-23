"""Insights registry on a fixed dataset: two runs on two endpoints, a requirement name
shared by two requirements, an errored result, numeric and text metric scores, and
results straddling midnight UTC at a month boundary."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from rhesis.backend.app import models

# (requirement, topic, category, verdict in run A, verdict in run B); None = errored
TESTS = [
    ("Refunds", "Billing", "Harmless", "pass", "pass"),
    ("Refunds", "Billing", "Harmless", "fail", "pass"),
    ("Refunds", "Claims", "Harmful", "pass", "fail"),
    ("Safety", "Claims", "Harmful", "fail", "fail"),
    ("Safety", "Greetings", "Harmless", "pass", None),
    ("Safety dup", "Greetings", "Harmful", "pass", "pass"),
    ("Safety dup", "Billing", "Harmless", None, "fail"),
]


@pytest.fixture
def dataset(
    test_db, test_organization, db_user, db_status, db_endpoint, test_type_lookup, db_project
):
    org_id, user_id = test_organization.id, db_user.id

    def add(obj):
        test_db.add(obj)
        test_db.flush()
        return obj

    def named(model, name, **kw):
        return add(model(name=name, organization_id=org_id, user_id=user_id, **kw))

    requirements = {
        "Refunds": named(models.Requirement, "Refunds"),
        "Safety": named(models.Requirement, "Safety"),
        "Safety dup": named(models.Requirement, "Safety"),
    }
    topics = {n: named(models.Topic, n) for n in ("Billing", "Claims", "Greetings")}
    categories = {n: named(models.Category, n) for n in ("Harmless", "Harmful")}
    test_sets = {n: named(models.TestSet, n) for n in ("Core", "Edge")}
    run_status = {
        n: named(models.Status, n, entity_type_id=test_type_lookup.id)
        for n in ("Completed", "Failed")
    }
    endpoint_b = add(
        models.Endpoint(
            name="Staging bot",
            connection_type=db_endpoint.connection_type,
            url=db_endpoint.url,
            method=db_endpoint.method,
            organization_id=org_id,
            user_id=user_id,
            status_id=db_status.id,
            project_id=db_project.id,
        )
    )

    runs = {}
    run_specs = [
        ("Run A", db_endpoint, "Core", "Completed", datetime(2026, 8, 31, 22, tzinfo=timezone.utc)),
        ("Run B", endpoint_b, "Edge", "Failed", datetime(2026, 9, 15, 10, tzinfo=timezone.utc)),
    ]
    for name, endpoint, test_set, run_state, started in run_specs:
        config = add(
            models.TestConfiguration(
                endpoint_id=endpoint.id,
                test_set_id=test_sets[test_set].id,
                organization_id=org_id,
                user_id=user_id,
            )
        )
        run = add(
            models.TestRun(
                name=name,
                organization_id=org_id,
                user_id=user_id,
                status_id=run_status[run_state].id,
                test_configuration_id=config.id,
                created_at=started,
            )
        )
        runs[name] = (run, config, started)

    tests = []
    for i, (req, topic, category, verdict_a, verdict_b) in enumerate(TESTS):
        test = add(
            models.Test(
                priority=1,
                organization_id=org_id,
                user_id=user_id,
                status_id=db_status.id,
                requirement_id=requirements[req].id,
                topic_id=topics[topic].id,
                category_id=categories[category].id,
            )
        )
        tests.append(test)
        for run_name, verdict in (("Run A", verdict_a), ("Run B", verdict_b)):
            run, config, started = runs[run_name]
            passed = verdict == "pass"
            add(
                models.TestResult(
                    test_id=test.id,
                    test_run_id=run.id,
                    test_configuration_id=config.id,
                    organization_id=org_id,
                    user_id=user_id,
                    status_id=db_status.id,
                    execution="ok" if verdict else "error",
                    verdict=verdict,
                    # Run A's results straddle midnight UTC, Aug 31 -> Sep 1.
                    created_at=started + timedelta(minutes=30 * i),
                    test_metrics={
                        "metrics": {
                            "Fluency": {"is_successful": passed, "score": 0.9 if passed else 0.3},
                            "Tone": {"is_successful": True, "score": "polite"},
                        }
                    },
                )
            )

    tests.append(
        add(
            models.Test(
                priority=2,
                organization_id=org_id,
                user_id=user_id,
                status_id=db_status.id,
                requirement_id=requirements["Refunds"].id,
                topic_id=topics["Claims"].id,
                category_id=categories["Harmful"].id,
            )
        )
    )
    test_db.commit()

    names = {str(o.id): label for label, o in requirements.items()}
    names.update({str(run.id): n for n, (run, _, _) in runs.items()})
    return {
        "run_ids": [str(run.id) for run, _, _ in runs.values()],
        "test_ids": [str(t.id) for t in tests],
        "names": names,
    }


@pytest.fixture
def query(authenticated_client, dataset):
    """GET /insights scoped to the dataset; returns the rows."""

    def _query(entity, group_by, measures, **params):
        scope = (
            {"test_ids": dataset["test_ids"]}
            if entity == "test"
            else {"test_run_ids": dataset["run_ids"]}
        )
        response = authenticated_client.get(
            "/insights/",
            params={
                "entity": entity,
                "group_by": group_by,
                "measures": measures,
                **scope,
                **params,
            },
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()["rows"]

    return _query


def _by(rows, key):
    return {row[key]: row for row in rows}


@pytest.mark.unit
class TestInsightsRegistry:
    def test_overall_pass_rate_excludes_errors(self, query):
        (row,) = query("test_result", [], ["count", "passed", "failed", "pass_rate"])
        assert row == {"count": 14, "passed": 7, "failed": 5, "pass_rate": 58.33}

    def test_same_named_requirements_stay_separate(self, query, dataset):
        rows = query("test_result", ["requirement"], ["count", "pass_rate"])
        by_id = {dataset["names"][r["requirement_id"]]: r for r in rows}
        assert by_id["Safety"]["requirement"] == by_id["Safety dup"]["requirement"] == "Safety"
        assert by_id["Safety"]["pass_rate"] == 33.33
        assert by_id["Safety dup"]["pass_rate"] == 66.67

    def test_two_dimensions_return_both_ids(self, query):
        rows = query("test_result", ["topic", "test_run"], ["count", "pass_rate"])
        claims_b = next(r for r in rows if r["topic"] == "Claims" and r["test_run"] == "Run B")
        assert claims_b["pass_rate"] == 0.0
        assert claims_b["topic_id"] and claims_b["test_run_id"]

    def test_endpoint_and_test_set_dimensions(self, query):
        by_set = _by(query("test_result", ["test_set"], ["count", "error_count"]), "test_set")
        assert by_set["Core"]["count"] == by_set["Edge"]["count"] == 7
        assert by_set["Edge"]["error_count"] == 1
        by_endpoint = _by(query("test_result", ["endpoint"], ["pass_rate"]), "endpoint")
        assert by_endpoint["Staging bot"]["pass_rate"] == 50.0

    @pytest.mark.parametrize(
        "grain, expected",
        [
            ("month", {"2026-08-01": 4, "2026-09-01": 10}),
            ("week", {"2026-08-31": 7, "2026-09-14": 7}),
            ("day", {"2026-08-31": 4, "2026-09-01": 3, "2026-09-15": 7}),
        ],
    )
    def test_period_buckets_in_utc(self, query, grain, expected):
        rows = query("test_result", ["period"], ["count"], time_grain=grain)
        assert {r["period"]: r["count"] for r in rows} == expected

    def test_order_limit_and_min_count(self, query):
        rows = query(
            "test_result",
            ["topic"],
            ["count", "pass_rate"],
            order_by=["pass_rate"],
            limit=2,
            min_count=4,
        )
        assert [(r["topic"], r["pass_rate"]) for r in rows] == [("Claims", 25.0), ("Billing", 60.0)]

    def test_descending_order(self, query):
        rows = query("test_result", ["topic"], ["pass_rate"], order_by=["-pass_rate"])
        assert [r["topic"] for r in rows] == ["Greetings", "Billing", "Claims"]

    def test_metric_scores_ignore_text_scores(self, query):
        rows = query("metric", ["metric", "test_run"], ["avg_score", "min_score", "max_score"])
        fluency_a = next(r for r in rows if r["metric"] == "Fluency" and r["test_run"] == "Run A")
        assert fluency_a == {**fluency_a, "avg_score": 0.6429, "min_score": 0.3, "max_score": 0.9}
        tone = [r for r in rows if r["metric"] == "Tone"]
        assert all(r["avg_score"] is None for r in tone)

    def test_metric_by_topic(self, query):
        rows = query("metric", ["metric", "topic"], ["pass_rate"], metric_names=["Fluency"])
        assert _by(rows, "topic")["Claims"]["pass_rate"] == 25.0

    def test_run_completion_comes_from_run_status(self, query):
        rows = query("test_run", ["status"], ["count", "completed", "failed", "completion_rate"])
        assert _by(rows, "status")["Completed"]["completion_rate"] == 100.0
        assert _by(rows, "status")["Failed"]["failed"] == 1

    def test_test_entity_sums_are_integers(self, query):
        rows = query("test", ["is_unrun"], ["count", "run_count", "passed", "failed"])
        ran = _by(rows, "is_unrun")[False]
        assert ran == {**ran, "count": 7, "run_count": 14, "passed": 7, "failed": 5}
        assert _by(rows, "is_unrun")[True]["count"] == 1


@pytest.mark.unit
class TestInsightsValidation:
    @pytest.mark.parametrize(
        "params",
        [
            {"entity": "test_result", "group_by": ["requirement_id"]},
            {"entity": "test_result", "group_by": ["year"]},
            {"entity": "metric", "group_by": ["metric_name"]},
            {"entity": "test_run", "measures": ["pass_rate"]},
            {"entity": "test_result", "time_grain": "fortnight", "group_by": ["period"]},
            {"entity": "test_result", "order_by": ["pass_rate"]},
            {"entity": "test_result", "limit": 0},
            {"entity": "test_result", "min_count": 0},
            {"entity": "test_result", "group_by": ["topic", "topic"]},
            {"entity": "test", "group_by": ["test_type_id"]},
        ],
    )
    def test_invalid_params_return_400(self, authenticated_client, params):
        response = authenticated_client.get("/insights/", params={"measures": ["count"], **params})
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    def test_repeated_dimension_is_named(self, authenticated_client):
        response = authenticated_client.get(
            "/insights/",
            params={"entity": "test_result", "group_by": ["topic", "topic"], "measures": ["count"]},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "['topic'] more than once" in response.json()["detail"]

    def test_schema_lists_the_registry(self, authenticated_client):
        from rhesis.backend.app.services.insights import REGISTRY

        response = authenticated_client.get("/insights/schema")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body["entities"]) == set(REGISTRY)
        result = body["entities"]["test_result"]
        assert result["dimensions"]["topic"]["has_id"] is True
        assert "period" in result["dimensions"]
        assert result["measures"]["pass_rate"]["kind"] == "rate"
        assert "endpoint_ids" in result["filters"]
        assert body["time_grains"] == ["day", "week", "month", "quarter", "year"]


@pytest.mark.unit
def test_sdk_docs_tables_match_the_registry():
    """docs/content/sdk/insights.mdx lists every entity's group_by, measures and filters by hand;
    this keeps it from drifting from the registry it documents."""
    import re
    from pathlib import Path

    from rhesis.backend.app.services.insights.registry import PERIOD, REGISTRY

    page = (Path(__file__).parents[3] / "docs/content/sdk/insights.mdx").read_text()
    rows = {}
    for line in page.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| `") and cells[0].strip("`") in REGISTRY:
            names = [set(re.findall(r"`([a-z0-9_]+)`", c)) for c in cells[1:]]
            rows.setdefault(cells[0].strip("`"), []).append(names)

    for entity, entry in REGISTRY.items():
        (_, group_by, measures), (filters,) = rows[entity]
        assert group_by == {*entry.dimensions, PERIOD}, entity
        assert measures == set(entry.measures), entity
        assert filters == set(entry.filters), entity


@pytest.fixture
def traces(test_db, test_organization, db_user, db_project, db_test_run):
    """Two traces from a test run (one with an errored span) and one production trace.

    Tokens sit on llm.invoke child spans and cost on every span's enriched_data, as
    ingestion and enrichment leave them, so the per-trace collapse is exercised.
    """
    from rhesis.backend.app.scope import RequestScope

    started = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)

    def span(trace_id, span_id, *, parent=None, env="development", ms, error=False, **extra):
        return models.Trace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent,
            project_id=db_project.id,
            organization_id=test_organization.id,
            environment=env,
            span_name="ai.llm.invoke" if parent else "chat",
            span_kind="INTERNAL",
            start_time=started,
            end_time=started + timedelta(milliseconds=ms),
            duration_ms=ms,
            status_code="ERROR" if error else "OK",
            events=[],
            links=[],
            resource={},
            **extra,
        )

    def llm(tokens):
        return {
            "ai.operation.type": "llm.invoke",
            "ai.llm.tokens.input": tokens[0],
            "ai.llm.tokens.output": tokens[1],
            "ai.llm.tokens.total": tokens[0] + tokens[1],
        }

    def cost(usd):
        return {"costs": {"total_cost_usd": usd}}

    run_id = db_test_run.id
    test_db.add_all(
        [
            span(
                "a" * 32,
                "a1" * 8,
                ms=1000,
                test_run_id=run_id,
                attributes={},
                enriched_data=cost(0.01),
            ),
            span(
                "a" * 32,
                "a2" * 8,
                parent="a1" * 8,
                ms=900,
                attributes=llm((100, 50)),
                enriched_data=cost(0.01),
            ),
            span(
                "b" * 32,
                "b1" * 8,
                ms=3000,
                test_run_id=run_id,
                attributes={},
                enriched_data=cost(0.03),
            ),
            span(
                "b" * 32,
                "b2" * 8,
                parent="b1" * 8,
                ms=2900,
                error=True,
                attributes=llm((200, 100)),
                enriched_data=cost(0.03),
            ),
            span("c" * 32, "c1" * 8, env="production", ms=500, attributes={}, enriched_data={}),
        ]
    )
    test_db.commit()

    previous = test_db.info.get("_scope")
    test_db.info["_scope"] = RequestScope(
        organization_id=str(test_organization.id),
        user_id=str(db_user.id),
        project_id=str(db_project.id),
    )
    yield db_test_run
    if previous is None:
        test_db.info.pop("_scope", None)
    else:
        test_db.info["_scope"] = previous


def _trace_rows(client, group_by, measures, **params):
    response = client.get(
        "/insights/",
        params={"entity": "trace", "group_by": group_by, "measures": measures, **params},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["rows"]


@pytest.mark.unit
class TestTraceEntity:
    def test_totals_count_each_trace_once(self, authenticated_client, traces):
        (row,) = _trace_rows(
            authenticated_client,
            [],
            ["count", "error_count", "error_rate", "tokens", "cost_usd", "avg_duration_ms"],
        )
        # Tokens from the llm.invoke spans only; cost once per trace, not per span row.
        assert row == {
            "count": 3,
            "error_count": 1,
            "error_rate": 33.33,
            "tokens": 450,
            "cost_usd": 0.04,
            "avg_duration_ms": 1500.0,
        }

    def test_by_test_run_and_endpoint(self, authenticated_client, traces):
        rows = _trace_rows(authenticated_client, ["test_run"], ["count", "p95_duration_ms"])
        by_run = {r["test_run_id"]: r for r in rows}
        assert by_run[str(traces.id)]["count"] == 2
        assert by_run[str(traces.id)]["test_run"] == traces.name
        assert by_run[None]["count"] == 1  # the production trace has no run

        (endpoint,) = _trace_rows(
            authenticated_client, ["endpoint"], ["count"], test_run_ids=[str(traces.id)]
        )
        assert endpoint["endpoint_id"] and endpoint["count"] == 2

    def test_by_environment_and_errors(self, authenticated_client, traces):
        rows = _trace_rows(authenticated_client, ["environment"], ["count", "cost_usd"])
        assert {r["environment"]: r["count"] for r in rows} == {"development": 2, "production": 1}

        rows = _trace_rows(
            authenticated_client, ["has_error"], ["count"], environments=["development"]
        )
        assert {r["has_error"]: r["count"] for r in rows} == {False: 1, True: 1}

    def test_ids_are_not_supported(self, authenticated_client, traces):
        response = authenticated_client.get("/insights/ids", params={"entity": "trace"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_projects_traces_are_left_out(
        self,
        authenticated_client,
        traces,
        test_db,
        test_organization,
        db_project,
        db_inactive_project,
    ):
        from tests.backend.fixtures.rls import scope_to_project

        started = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
        scope_to_project(test_db, db_inactive_project.id)
        test_db.add(
            models.Trace(
                trace_id="d" * 32,
                span_id="d1" * 8,
                project_id=db_inactive_project.id,
                organization_id=test_organization.id,
                environment="development",
                span_name="chat",
                span_kind="INTERNAL",
                start_time=started,
                end_time=started,
                duration_ms=1,
                status_code="OK",
                attributes={},
                events=[],
                links=[],
                resource={},
            )
        )
        test_db.commit()
        scope_to_project(test_db, db_project.id)

        (row,) = _trace_rows(authenticated_client, [], ["count"])
        assert row["count"] == 3

    def test_date_window_bounds_the_traces(self, authenticated_client, traces):
        (row,) = _trace_rows(
            authenticated_client, [], ["count"], start_date="2026-09-16T00:00:00+00:00"
        )
        assert row["count"] == 0
        (row,) = _trace_rows(
            authenticated_client, [], ["count"], end_date="2026-09-16T00:00:00+00:00"
        )
        assert row["count"] == 3
