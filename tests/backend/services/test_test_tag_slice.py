"""Running part of a test set: only the tests carrying any of the run's test tags."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.crud.test_run import get_ordered_tests_for_test_set
from rhesis.backend.app.models.tag import Tag, TaggedItem
from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.schemas.test_set import TestSetExecutionRequest
from rhesis.backend.app.services.run_config import RUN_CONFIG_KEY, snapshot_run_config
from rhesis.backend.app.services.test_run_schedule.errors import ScheduleValidationError
from rhesis.backend.app.services.test_run_schedule.service import _settings_attributes
from rhesis.backend.app.services.test_set import (
    _validate_reference_test_run,
    _validate_test_set_not_empty,
    count_test_set_tests,
    execute_test_set_on_endpoint,
    filter_tests_by_tags,
    run_tests_tagged,
    tagged_test_filter,
)


@pytest.fixture
def tagged_set(test_db, test_organization, db_user, db_status):
    """Four tests: two tagged "smoke", one "smoke" and "billing", one untagged."""
    org_id, user_id = test_organization.id, db_user.id
    test_set = TestSet(
        name="tag-slice-set", user_id=user_id, organization_id=org_id, status_id=db_status.id
    )
    test_db.add(test_set)
    tags = {
        name: Tag(name=name, organization_id=org_id, user_id=user_id)
        for name in ("smoke", "billing")
    }
    test_db.add_all(tags.values())
    test_db.flush()

    tests = {}
    for key, tag_names in (
        ("a", ["smoke"]),
        ("b", ["smoke"]),
        ("c", ["smoke", "billing"]),
        ("d", []),
    ):
        test = Test(user_id=user_id, organization_id=org_id, status_id=db_status.id)
        test_db.add(test)
        test_db.flush()
        test_db.execute(
            test_test_set_association.insert().values(
                test_id=test.id, test_set_id=test_set.id, organization_id=org_id, user_id=user_id
            )
        )
        for name in tag_names:
            test_db.add(
                TaggedItem(
                    tag_id=tags[name].id,
                    entity_id=test.id,
                    entity_type="Test",
                    organization_id=org_id,
                    user_id=user_id,
                )
            )
        tests[key] = test
    test_db.commit()
    return test_set, tests


def test_count_matches_any_tag(test_db, tagged_set):
    test_set, _ = tagged_set
    assert count_test_set_tests(test_db, test_set.id) == 4
    assert count_test_set_tests(test_db, test_set.id, ["smoke"]) == 3
    assert count_test_set_tests(test_db, test_set.id, ["billing"]) == 1
    # A test with both tags counts once.
    assert count_test_set_tests(test_db, test_set.id, ["smoke", "billing"]) == 3
    assert count_test_set_tests(test_db, test_set.id, ["missing"]) == 0


def test_count_skips_deleted_tests(test_db, tagged_set):
    test_set, tests = tagged_set
    tests["a"].deleted_at = datetime.now(timezone.utc)
    test_db.commit()
    assert count_test_set_tests(test_db, test_set.id, ["smoke"]) == 2


def test_filter_keeps_tagged_tests(test_db, tagged_set):
    test_set, tests = tagged_set
    everything = list(tests.values())
    assert filter_tests_by_tags(test_db, test_set.id, everything, []) == everything
    kept = filter_tests_by_tags(test_db, test_set.id, everything, ["billing"])
    assert [t.id for t in kept] == [tests["c"].id]


def test_ordered_tests_follow_the_slice(test_db, tagged_set, test_org_id):
    test_set, tests = tagged_set
    ordered = get_ordered_tests_for_test_set(test_db, test_set.id, test_org_id, ["smoke"])
    assert {test_id for test_id, _, _ in ordered} == {str(tests[k].id) for k in ("a", "b", "c")}


def test_empty_slice_names_the_tags(test_db, tagged_set):
    test_set, _ = tagged_set
    _validate_test_set_not_empty(test_db, test_set, ["smoke"])
    with pytest.raises(ValueError, match="carry the tags: missing"):
        _validate_test_set_not_empty(test_db, test_set, ["missing"])


def test_filter_reads_only_a_list_of_strings():
    assert tagged_test_filter(None) == []
    assert tagged_test_filter({"tests_tagged": "smoke"}) == []
    assert tagged_test_filter({"tests_tagged": ["smoke", 3]}) == ["smoke"]


def test_request_cleans_tags():
    request = TestSetExecutionRequest(tests_tagged=[" smoke ", "", "smoke", "billing"])
    assert request.tests_tagged == ["smoke", "billing"]


def test_request_limits_tag_count():
    with pytest.raises(ValueError):
        TestSetExecutionRequest(tests_tagged=[f"t{i}" for i in range(21)])


def test_schedule_keeps_tags_and_drops_stray_option(test_db, tagged_set):
    test_set, _ = tagged_set
    settings = TestSetExecutionRequest(
        execution_options={"execution_mode": "Parallel", "tests_tagged": ["billing"]},
        tests_tagged=["smoke"],
    )
    attributes = _settings_attributes(test_db, test_set.id, settings)
    assert attributes["tests_tagged"] == ["smoke"]


def test_schedule_refuses_an_empty_slice(test_db, tagged_set):
    test_set, _ = tagged_set
    with pytest.raises(ScheduleValidationError, match="carry the tags"):
        _settings_attributes(
            test_db, test_set.id, TestSetExecutionRequest(tests_tagged=["missing"])
        )


def test_run_snapshot_records_the_slice():
    class _Config:
        attributes = {"execution_mode": "Parallel", "tests_tagged": ["smoke"]}

    attributes = snapshot_run_config(test_config=_Config(), attributes={})
    assert attributes[RUN_CONFIG_KEY]["tests_tagged"] == ["smoke"]


def test_set_lists_its_test_tags_with_counts(test_db, tagged_set):
    from rhesis.backend.app.crud.test_set import get_test_set_test_tags

    test_set, _ = tagged_set
    assert get_test_set_test_tags(test_db, test_set.id) == [("billing", 1), ("smoke", 3)]


def _user(test_set):
    user = MagicMock()
    user.id = test_set.user_id
    user.organization_id = test_set.organization_id
    return user


def _run_with(test_db, test_set, endpoint, *, snapshot_tags=None, config_tags=None):
    config = TestConfiguration(
        test_set_id=test_set.id,
        endpoint_id=endpoint.id,
        organization_id=test_set.organization_id,
        user_id=test_set.user_id,
        attributes={"tests_tagged": config_tags} if config_tags is not None else {},
    )
    test_db.add(config)
    test_db.flush()
    run = TestRun(
        test_configuration_id=config.id,
        organization_id=test_set.organization_id,
        user_id=test_set.user_id,
        attributes=(
            {"run_config": {"tests_tagged": snapshot_tags}} if snapshot_tags is not None else {}
        ),
    )
    test_db.add(run)
    test_db.commit()
    return run


def test_a_run_reports_its_own_snapshot_over_the_live_config(test_db, tagged_set, db_endpoint):
    test_set, _ = tagged_set
    run = _run_with(test_db, test_set, db_endpoint, snapshot_tags=["smoke"], config_tags=[])
    assert run_tests_tagged(run) == ["smoke"]
    legacy = _run_with(test_db, test_set, db_endpoint, config_tags=["billing"])
    assert run_tests_tagged(legacy) == ["billing"]


def test_reused_run_must_cover_the_new_runs_tests(test_db, tagged_set, db_endpoint):
    test_set, _ = tagged_set
    reference = _run_with(test_db, test_set, db_endpoint, snapshot_tags=["smoke"])
    user = _user(test_set)

    # "billing" is a subset of "smoke" here, so its outputs are all there.
    _validate_reference_test_run(test_db, reference.id, test_set, user, ["billing"])
    _validate_reference_test_run(test_db, reference.id, test_set, user, ["smoke"])
    with pytest.raises(ValueError, match="only ran the tests tagged smoke"):
        _validate_reference_test_run(test_db, reference.id, test_set, user, [])


@patch("rhesis.backend.app.services.test_set._submit_test_configuration_for_execution")
def test_execute_stores_the_tags_on_the_configuration(
    mock_submit, test_db, tagged_set, db_endpoint
):
    test_set, _ = tagged_set
    mock_submit.return_value = (MagicMock(id=str(uuid.uuid4())), str(uuid.uuid4()), "run")

    result = execute_test_set_on_endpoint(
        db=test_db,
        test_set_identifier=str(test_set.id),
        endpoint_id=db_endpoint.id,
        current_user=_user(test_set),
        organization_id=str(test_set.organization_id),
        user_id=str(test_set.user_id),
        test_configuration_attributes={"execution_mode": "Parallel", "tests_tagged": ["x"]},
        tests_tagged=["smoke"],
    )

    config = test_db.get(TestConfiguration, uuid.UUID(result["test_configuration_id"]))
    assert config.attributes["tests_tagged"] == ["smoke"]


def test_execute_refuses_tags_no_test_carries(test_db, tagged_set, db_endpoint):
    test_set, _ = tagged_set
    with pytest.raises(ValueError, match="carry the tags: missing"):
        execute_test_set_on_endpoint(
            db=test_db,
            test_set_identifier=str(test_set.id),
            endpoint_id=db_endpoint.id,
            current_user=_user(test_set),
            tests_tagged=["missing"],
        )


def test_route_lists_test_tags(authenticated_client, tagged_set):
    test_set, _ = tagged_set
    response = authenticated_client.get(f"/test_sets/{test_set.id}/test-tags")
    assert response.status_code == 200
    assert response.json() == [
        {"name": "billing", "test_count": 1},
        {"name": "smoke", "test_count": 3},
    ]


def test_route_passes_tags_to_execution(authenticated_client, tagged_set, db_endpoint):
    test_set, _ = tagged_set
    with patch(
        "rhesis.backend.app.routers.test_set.execute_test_set_on_endpoint",
        return_value={"status": "submitted"},
    ) as execute:
        response = authenticated_client.post(
            f"/test_sets/{test_set.id}/execute/{db_endpoint.id}",
            json={"tests_tagged": ["smoke"]},
        )
    assert response.status_code == 200, response.text
    assert execute.call_args.kwargs["tests_tagged"] == ["smoke"]
