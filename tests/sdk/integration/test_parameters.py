"""Integration tests for Parameters and Experiments.

Requires the test backend to be running (``cd sdk && make docker-up``).
"""

import pytest
import requests

from rhesis.sdk import Parameters
from rhesis.sdk.entities import Experiment, Projects
from rhesis.sdk.models.parameters import (
    NumberValue,
    ParameterField,
    ParameterSchema,
    StringValue,
    canonical_version,
    validate_values_against_schema,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

TEST_PROJECT_ID = "12340000-0000-4000-8000-000000001234"


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
    assert "version" in version_data
    assert version_data["version"].startswith("v_")
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
