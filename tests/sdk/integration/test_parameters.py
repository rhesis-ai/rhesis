"""Integration tests for Parameters and Experiments.

Requires the test backend to be running (``cd sdk && make docker-up``).
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
import requests as _requests
import time
import uuid

from rhesis.sdk import Parameters
from rhesis.sdk.entities import Experiment, Project, Projects
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models.parameters import (
    NumberValue,
    ParameterField,
    ParameterSchema,
    StringValue,
    canonical_version,
    validate_values_against_schema,
)

_real_request = _requests.request


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

TEST_PROJECT_ID = "12340000-0000-4000-8000-000000001234"


def _unique_project_name() -> str:
    """Generate a unique project name for tests to avoid naming conflicts."""
    return f"Test Project {uuid.uuid4().hex[:8]} {int(time.time() * 1000)}"


def _test_schema() -> ParameterSchema:
    return ParameterSchema(
        fields=[
            ParameterField(
                name="model",
                type="string",
                default="gpt-4o-mini",
            ),
            ParameterField(
                name="temperature",
                type="number",
                default=0.7,
            ),
            ParameterField(
                name="mode",
                type="enum",
                default="text",
                options=["text", "json"],
            ),
        ]
    )


# ------------------------------------------------------------------ #
# Schema CRUD                                                         #
# ------------------------------------------------------------------ #


def test_put_and_get_schema(docker_compose_test_env):
    """Push a schema, then read it back."""
    schema = _test_schema()
    Parameters.put_schema(TEST_PROJECT_ID, schema)

    fetched = Parameters.schema(TEST_PROJECT_ID)
    names = {f.name for f in fetched.fields}
    assert {"model", "temperature", "mode"} <= names


# ------------------------------------------------------------------ #
# Experiment lifecycle                                                 #
# ------------------------------------------------------------------ #


def test_experiment_crud(docker_compose_test_env):
    """Create → commit → pull back an experiment."""
    # Ensure schema exists
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(
        name="integration-crud",
        project_id=TEST_PROJECT_ID,
        description="Integration test experiment",
    )
    result = exp.push()
    assert exp.id is not None
    assert result["name"] == "integration-crud"

    # Commit with bare values (Option A ergonomics)
    version_data = exp.commit(
        {"model": "gpt-4o", "temperature": 0.9},
        message="first commit",
    )
    assert version_data["version"] == "v1"
    assert "content_hash" in version_data
    assert exp.latest_version == version_data["version"]

    # Read back
    exp.pull()
    assert exp.name == "integration-crud"

    # Cleanup
    exp.delete()


def test_experiment_share_and_promote(docker_compose_test_env):
    """Share → promote → resolve via environment."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(
        name="integration-promote",
        project_id=TEST_PROJECT_ID,
    )
    exp.push()
    exp.commit({"model": "claude-sonnet", "temperature": 0.5})
    exp.share()
    exp.promote(environment="default")

    # Resolve through Parameters facade
    Parameters.invalidate(TEST_PROJECT_ID)
    params = Parameters.get(TEST_PROJECT_ID, environment="default")

    assert params["model"] == "claude-sonnet"
    assert params["temperature"] == 0.5
    assert params.source == "environment"
    assert params.source_environment == "default"
    assert str(params.experiment_id) == str(exp.id)

    # Typed accessors
    assert params.get_string("model") == "claude-sonnet"
    assert params.get_number("temperature") == 0.5
    assert params.get_str("model") == "claude-sonnet"

    # Cleanup
    exp.delete()


def test_experiment_version_pinning(docker_compose_test_env):
    """Pin to a specific version and resolve it."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(
        name="integration-pin",
        project_id=TEST_PROJECT_ID,
    )
    exp.push()

    v1 = exp.commit({"model": "v1-model", "temperature": 0.3})
    v1_hash = v1["version"]

    v2 = exp.commit(
        {"model": "v2-model", "temperature": 0.8},
        parent_version=v1_hash,
    )
    v2_hash = v2["version"]

    exp.share()
    exp.promote(environment="default")

    # Environment resolves to latest (v2)
    Parameters.invalidate()
    params_latest = Parameters.get(TEST_PROJECT_ID, environment="default")
    assert params_latest["model"] == "v2-model"

    # Pin resolves to v1
    params_pinned = Parameters.get(TEST_PROJECT_ID, version=v1_hash)
    assert params_pinned["model"] == "v1-model"
    assert params_pinned.version == v1_hash

    # Cleanup
    exp.delete()


def test_experiment_publish_shorthand(docker_compose_test_env):
    """Experiment.publish() does create→commit→share→promote in one call."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-publish",
        project_id=TEST_PROJECT_ID,
        values={"model": "published-model", "temperature": 0.6},
        message="one-liner publish",
        environment="default",
    )

    assert exp.id is not None
    assert exp.latest_version is not None

    Parameters.invalidate()
    params = Parameters.get(TEST_PROJECT_ID, environment="default")
    assert params["model"] == "published-model"
    assert params["temperature"] == 0.6

    # Cleanup
    exp.delete()


# ------------------------------------------------------------------ #
# Environments                                                         #
# ------------------------------------------------------------------ #


def test_environments_round_trip(docker_compose_test_env):
    """Bind an environment and read it back."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-environments",
        project_id=TEST_PROJECT_ID,
        values={"model": "environment-test"},
        environment="default",
    )

    # Read environments
    envs = Parameters.environments(TEST_PROJECT_ID)
    assert "default" in envs.environments
    ep = envs.environments["default"]
    assert str(ep.experiment_id) == str(exp.id)
    assert ep.version == exp.latest_version

    # Bind a different environment
    Parameters.put_environment(
        TEST_PROJECT_ID,
        "staging",
        experiment_id=str(exp.id),
        version=exp.latest_version,
    )
    envs2 = Parameters.environments(TEST_PROJECT_ID)
    assert "staging" in envs2.environments

    # Cleanup
    exp.delete()


# ------------------------------------------------------------------ #
# Version history                                                      #
# ------------------------------------------------------------------ #


def test_experiment_version_history(docker_compose_test_env):
    """Multiple commits produce distinct immutable versions."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(
        name="integration-history",
        project_id=TEST_PROJECT_ID,
    )
    exp.push()

    v1 = exp.commit({"temperature": 0.3}, message="cold")
    v2 = exp.commit(
        {"temperature": 0.9},
        message="hot",
        parent_version=v1["version"],
    )

    assert v1["version"] != v2["version"]

    # Fetch individual version
    fetched = exp.get_version(v1["version"])
    assert fetched["version"] == v1["version"]
    assert fetched["message"] == "cold"

    # Latest version
    latest = exp.latest_version_data()
    assert latest["version"] == v2["version"]

    # Cleanup
    exp.delete()


# ------------------------------------------------------------------ #
# Cache behaviour                                                      #
# ------------------------------------------------------------------ #


def test_cache_invalidation(docker_compose_test_env):
    """Invalidating the cache forces a fresh fetch."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-cache",
        project_id=TEST_PROJECT_ID,
        values={"model": "cached-v1"},
        environment="default",
    )

    Parameters.invalidate()
    p1 = Parameters.get(TEST_PROJECT_ID, environment="default")
    assert p1["model"] == "cached-v1"

    # Update with new version
    exp.commit({"model": "cached-v2"})
    exp.promote(environment="default")

    # Cached value should still be v1
    p_cached = Parameters.get(TEST_PROJECT_ID, environment="default")
    assert p_cached["model"] == "cached-v1"

    # After invalidation, should see v2
    Parameters.invalidate(TEST_PROJECT_ID)
    p_fresh = Parameters.get(TEST_PROJECT_ID, environment="default")
    assert p_fresh["model"] == "cached-v2"

    # Cleanup
    exp.delete()


# ------------------------------------------------------------------ #
# ResolvedParameters ergonomics                                        #
# ------------------------------------------------------------------ #


def test_experiment_list_versions(docker_compose_test_env):
    """list_versions() returns the full version history."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(name="integration-list-versions", project_id=TEST_PROJECT_ID)
    exp.push()
    v1 = exp.commit({"temperature": 0.3}, message="first")
    v2 = exp.commit(
        {"temperature": 0.9},
        message="second",
        parent_version=v1["version"],
    )

    versions = exp.list_versions()
    assert len(versions) == 2
    assert versions[0]["version"] == v1["version"]
    assert versions[1]["version"] == v2["version"]

    exp.delete()


def test_experiment_results(docker_compose_test_env):
    """results() returns aggregated run data (empty when no runs exist)."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-results",
        project_id=TEST_PROJECT_ID,
        values={"model": "results-test"},
        environment="default",
    )

    by_run = exp.results(group_by="run")
    assert "items" in by_run
    assert isinstance(by_run["items"], list)

    by_version = exp.results(group_by="version")
    assert "items" in by_version
    assert isinstance(by_version["items"], list)

    exp.delete()


def test_experiment_delete_cascades_environments(docker_compose_test_env):
    """Deleting a promoted experiment auto-unbinds its environments."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-cascade-delete",
        project_id=TEST_PROJECT_ID,
        values={"model": "cascade-test"},
        environment="default",
    )

    # Verify environment is bound
    envs = Parameters.environments(TEST_PROJECT_ID)
    assert envs.environments.get("default") is not None

    # Delete should succeed without 409 — backend cascades automatically
    result = exp.delete()
    assert result is True


def test_resolved_parameters_mapping_protocol(docker_compose_test_env):
    """ResolvedParameters acts as a dict-like mapping."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-mapping",
        project_id=TEST_PROJECT_ID,
        values={
            "model": "mapping-test",
            "temperature": 0.42,
            "mode": "json",
        },
        environment="default",
    )

    Parameters.invalidate()
    p = Parameters.get(TEST_PROJECT_ID, environment="default")

    # Dict-style access
    assert p["model"] == "mapping-test"
    assert p["temperature"] == 0.42
    assert "model" in p
    assert "nonexistent" not in p
    assert p.get("missing", "fallback") == "fallback"

    # as_native() returns a plain dict
    native = p.as_native()
    assert isinstance(native, dict)
    assert native["mode"] == "json"

    # Cleanup
    exp.delete()


# ------------------------------------------------------------------ #
# Name-based resolution & Project entity                              #
# ------------------------------------------------------------------ #


def test_parameters_get_by_project_name(docker_compose_test_env):
    """Parameters.get() accepts a project name and resolves it to a UUID."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-name-lookup",
        project_id=TEST_PROJECT_ID,
        values={"model": "name-lookup-model", "temperature": 0.55},
        environment="default",
    )

    Parameters.invalidate()
    params = Parameters.get("Test Project", environment="default")

    assert params["model"] == "name-lookup-model"
    assert params["temperature"] == 0.55

    exp.delete()


def test_parameters_get_by_project_id_kwarg(docker_compose_test_env):
    """Parameters.get(project_id=...) works with the explicit keyword."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-project-id-kwarg",
        project_id=TEST_PROJECT_ID,
        values={"model": "kwarg-model", "temperature": 0.33},
        environment="default",
    )

    Parameters.invalidate()
    params = Parameters.get(project_id=TEST_PROJECT_ID, environment="default")

    assert params["model"] == "kwarg-model"
    assert params["temperature"] == 0.33

    exp.delete()


def test_resolved_parameters_dot_access(docker_compose_test_env):
    """ResolvedParameters supports attribute-style dot access."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-dot-access",
        project_id=TEST_PROJECT_ID,
        values={"model": "dot-model", "temperature": 0.77, "mode": "json"},
        environment="default",
    )

    Parameters.invalidate()
    params = Parameters.get(TEST_PROJECT_ID, environment="default")

    assert params.model == "dot-model"
    assert params.temperature == 0.77
    assert params.mode == "json"

    exp.delete()


def test_project_entity_parameters(docker_compose_test_env):
    """Project.parameters() resolves parameters through the entity."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment.publish(
        name="integration-entity-params",
        project_id=TEST_PROJECT_ID,
        values={"model": "entity-model", "temperature": 0.61},
        environment="default",
    )

    project = Projects.pull(name="Test Project")
    Parameters.invalidate()
    params = project.parameters(environment="default")

    assert params.model == "entity-model"
    assert params.temperature == 0.61
    assert params.source == "environment"

    exp.delete()


def test_project_entity_parameter_schema(docker_compose_test_env):
    """Project.parameter_schema() reads the schema through the entity."""
    schema = _test_schema()
    Parameters.put_schema(TEST_PROJECT_ID, schema)

    project = Projects.pull(name="Test Project")
    fetched = project.parameter_schema()

    names = {f.name for f in fetched.fields}
    assert {"model", "temperature", "mode"} <= names


def test_project_entity_put_parameter_schema(docker_compose_test_env):
    """Project.put_parameter_schema() writes a schema through the entity."""
    project = Projects.pull(name="Test Project")

    schema = _test_schema()
    project.put_parameter_schema(schema)

    fetched = project.parameter_schema()
    names = {f.name for f in fetched.fields}
    assert {"model", "temperature", "mode"} <= names


def test_parameters_schema_by_name(docker_compose_test_env):
    """Parameters.schema() and put_schema() accept project names."""
    Parameters.put_schema("Test Project", _test_schema())

    fetched = Parameters.schema("Test Project")
    names = {f.name for f in fetched.fields}
    assert {"model", "temperature", "mode"} <= names


# ------------------------------------------------------------------ #
# Experiment execution ergonomics                                      #
# ------------------------------------------------------------------ #


def _mock_execute_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "submitted", "task_id": "mock-task"}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _selective_mock(mock_resp):
    def _side_effect(*args, **kwargs):
        url = kwargs.get("url", args[1] if len(args) > 1 else "")
        if "/execute/" in url:
            return mock_resp
        return _real_request(*args, **kwargs)

    return _side_effect


def _create_test_endpoint() -> Endpoint:
    ep = Endpoint(
        name="Param Exec Endpoint",
        description="For parameter execution tests",
        connection_type="REST",
        url="https://httpbin.org/post",
        project_id=TEST_PROJECT_ID,
        method="POST",
        endpoint_path="/v1/chat",
        request_mapping={"message": "{{ input }}"},
        response_mapping={"output": "result.text"},
    )
    ep.push()
    return ep


def _create_test_set() -> TestSet:
    ts = TestSet(
        name="Param Exec Tests",
        description="For parameter execution tests",
        short_description="Test",
        test_set_type=TestType.SINGLE_TURN,
        tests=[
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Compliance",
                "prompt": {"content": "Hello, is this safe?"},
            }
        ],
    )
    ts.push()
    return ts


@patch("requests.request")
def test_execute_with_experiment_object(mock_request, docker_compose_test_env):
    """TestSet.execute(endpoint, experiment=exp) sends experiment_id and version."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())
    mock_request.side_effect = _selective_mock(_mock_execute_response())

    exp = Experiment(name="exec-object-test", project_id=TEST_PROJECT_ID)
    exp.push()
    v = exp.commit({"model": "gpt-4o", "temperature": 0.8})

    ts = _create_test_set()
    ep = _create_test_endpoint()

    result = ts.execute(ep, experiment=exp)

    assert result is not None
    assert result["status"] == "submitted"

    execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
    assert len(execute_calls) == 1
    body = execute_calls[0][1]["json"]
    assert body["experiment_id"] == str(exp.id)
    assert body["version"] == v["version"]

    exp.delete()


@patch("requests.request")
def test_execute_with_inline_parameters(mock_request, docker_compose_test_env):
    """TestSet.execute(endpoint, experiment=exp, parameters={...}) auto-commits."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())
    mock_request.side_effect = _selective_mock(_mock_execute_response())

    exp = Experiment(name="exec-inline-test", project_id=TEST_PROJECT_ID)
    exp.push()
    exp.commit({"model": "gpt-4o", "temperature": 0.5})
    original_version = exp.latest_version

    ts = _create_test_set()
    ep = _create_test_endpoint()

    result = ts.execute(
        ep, experiment=exp, parameters={"model": "claude-sonnet", "temperature": 0.9}
    )

    assert result["status"] == "submitted"
    # latest_version should have changed (new commit happened)
    assert exp.latest_version != original_version

    execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
    body = execute_calls[0][1]["json"]
    assert body["experiment_id"] == str(exp.id)
    assert body["version"] == exp.latest_version

    exp.delete()


@patch("requests.request")
def test_experiment_run_method(mock_request, docker_compose_test_env):
    """Experiment.run(test_set, endpoint) delegates to execute."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())
    mock_request.side_effect = _selective_mock(_mock_execute_response())

    exp = Experiment(name="exp-run-test", project_id=TEST_PROJECT_ID)
    exp.push()
    v = exp.commit({"model": "gpt-4o", "temperature": 0.7})

    ts = _create_test_set()
    ep = _create_test_endpoint()

    result = exp.run(ts, ep)

    assert result is not None
    assert result["status"] == "submitted"

    execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
    body = execute_calls[0][1]["json"]
    assert body["experiment_id"] == str(exp.id)
    assert body["version"] == v["version"]

    exp.delete()


@patch("requests.request")
def test_experiment_run_with_inline_parameters(mock_request, docker_compose_test_env):
    """Experiment.run(test_set, endpoint, parameters={...}) commits then executes."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())
    mock_request.side_effect = _selective_mock(_mock_execute_response())

    exp = Experiment(name="exp-run-inline-test", project_id=TEST_PROJECT_ID)
    exp.push()
    exp.commit({"temperature": 0.3})

    ts = _create_test_set()
    ep = _create_test_endpoint()

    result = exp.run(ts, ep, parameters={"temperature": 0.99})

    assert result["status"] == "submitted"

    execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
    body = execute_calls[0][1]["json"]
    assert body["version"] == exp.latest_version

    # Verify the inline commit actually happened
    fetched = exp.get_version(exp.latest_version)
    assert fetched["values"]["temperature"]["value"] == 0.99

    exp.delete()


def test_execute_experiment_and_experiment_id_conflict(docker_compose_test_env):
    """Passing both experiment= and experiment_id= raises ValueError."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(name="conflict-test", project_id=TEST_PROJECT_ID)
    exp.push()
    exp.commit({"temperature": 0.5})

    ts = _create_test_set()
    ep = _create_test_endpoint()

    with pytest.raises(ValueError, match="Pass 'experiment' or 'experiment_id', not both"):
        ts.execute(ep, experiment=exp, experiment_id=str(exp.id))

    exp.delete()


def test_execute_parameters_without_experiment_raises(docker_compose_test_env):
    """Passing parameters= without experiment= raises ValueError."""
    ts = _create_test_set()
    ep = _create_test_endpoint()

    with pytest.raises(ValueError, match="parameters= requires experiment="):
        ts.execute(ep, parameters={"temperature": 0.9})


def test_execute_experiment_no_versions_raises(docker_compose_test_env):
    """Passing an experiment with no versions raises ValueError."""
    Parameters.put_schema(TEST_PROJECT_ID, _test_schema())

    exp = Experiment(name="no-versions-test", project_id=TEST_PROJECT_ID)
    exp.push()

    ts = _create_test_set()
    ep = _create_test_endpoint()

    with pytest.raises(ValueError, match="Experiment has no versions"):
        ts.execute(ep, experiment=exp)

    exp.delete()
