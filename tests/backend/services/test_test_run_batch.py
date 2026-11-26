"""Starting a group of test runs on the server: one per set and experiment, one batch id."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from rhesis.backend.app.models.tag import Tag, TaggedItem
from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.schemas.test_run_batch import TestRunBatchCreate
from rhesis.backend.app.services.test_run_batch import start_batch

BATCH = "rhesis.backend.app.services.test_run_batch"


@pytest.fixture
def org_sets(test_db, test_organization, db_user, db_status):
    """Sets "alpha" and "beta" tagged "nightly", "gamma" untagged; alpha's 2 tests are "smoke"."""
    org_id, user_id = test_organization.id, db_user.id

    def tag(name):
        found = test_db.query(Tag).filter(Tag.name == name, Tag.organization_id == org_id).first()
        if found:
            return found
        created = Tag(name=name, organization_id=org_id, user_id=user_id)
        test_db.add(created)
        test_db.flush()
        return created

    def link(tag_name, entity_id, entity_type):
        test_db.add(
            TaggedItem(
                tag_id=tag(tag_name).id,
                entity_id=entity_id,
                entity_type=entity_type,
                organization_id=org_id,
                user_id=user_id,
            )
        )

    sets = {}
    for name, test_count, set_tags, test_tags in (
        ("alpha", 2, ["nightly"], ["smoke"]),
        ("beta", 3, ["nightly"], []),
        ("gamma", 1, [], []),
    ):
        test_set = TestSet(
            name=name, user_id=user_id, organization_id=org_id, status_id=db_status.id
        )
        test_db.add(test_set)
        test_db.flush()
        for tag_name in set_tags:
            link(tag_name, test_set.id, "TestSet")
        for _ in range(test_count):
            test = Test(user_id=user_id, organization_id=org_id, status_id=db_status.id)
            test_db.add(test)
            test_db.flush()
            test_db.execute(
                test_test_set_association.insert().values(
                    test_id=test.id,
                    test_set_id=test_set.id,
                    organization_id=org_id,
                    user_id=user_id,
                )
            )
            for tag_name in test_tags:
                link(tag_name, test.id, "Test")
        sets[name] = test_set
    test_db.commit()
    return sets


@pytest.fixture
def user(org_sets):
    test_set = org_sets["alpha"]
    member = MagicMock()
    member.id = test_set.user_id
    member.organization_id = test_set.organization_id
    return member


def _prepared(db, config, user):
    run = MagicMock()
    run.id = uuid.uuid4()
    run.name = f"run-{config.id.hex[:6]}"
    return run, str(uuid.uuid4())


@pytest.fixture
def submit():
    """Runs are prepared and queued without models, experiments or a broker."""
    with (
        patch(f"{BATCH}.prepare_run", side_effect=_prepared) as prepare,
        patch(f"{BATCH}.dispatch_run") as dispatch,
    ):
        yield MagicMock(
            prepare=prepare, dispatch=dispatch, assert_not_called=dispatch.assert_not_called
        )


def _configs(test_db, result):
    return [
        test_db.get(TestConfiguration, uuid.UUID(str(m["test_configuration_id"])))
        for m in result["members"]
    ]


def test_a_tag_runs_every_set_carrying_it(test_db, org_sets, user, submit, db_endpoint):
    result = start_batch(
        test_db,
        user,
        TestRunBatchCreate(test_set_tag="nightly", endpoint_id=db_endpoint.id),
    )

    assert [m["test_set_name"] for m in result["members"]] == ["alpha", "beta"]
    attributes = [c.attributes for c in _configs(test_db, result)]
    assert {a["batch_id"] for a in attributes} == {result["batch_id"]}
    assert [a["batch_index"] for a in attributes] == [0, 1]
    assert all(a["batch_size"] == 2 and a["batch_set_tag"] == "nightly" for a in attributes)


def test_each_set_runs_once_per_experiment(test_db, org_sets, user, submit, db_endpoint):
    experiments = [{"experiment_id": str(uuid.uuid4()), "version": v} for v in ("v1", "v2")]
    result = start_batch(
        test_db,
        user,
        TestRunBatchCreate(
            test_set_ids=[org_sets["alpha"].id, org_sets["gamma"].id],
            endpoint_id=db_endpoint.id,
            experiments=experiments,
        ),
    )

    assert [(m["test_set_name"], m["version"]) for m in result["members"]] == [
        ("alpha", "v1"),
        ("alpha", "v2"),
        ("gamma", "v1"),
        ("gamma", "v2"),
    ]
    configs = _configs(test_db, result)
    assert [c.attributes["parameters_ref"]["version"] for c in configs] == ["v1", "v2"] * 2
    assert all(len(c.attributes["batch_experiments"]) == 2 for c in configs)


def test_a_member_refused_while_preparing_starts_nothing(
    test_db, org_sets, user, submit, db_endpoint
):
    calls = []

    def refuse_second(db, config, member):
        calls.append(config.id)
        if len(calls) == 2:
            raise ValueError("Experiment version not found")
        return _prepared(db, config, member)

    submit.prepare.side_effect = refuse_second
    with pytest.raises(ValueError, match="version not found"):
        start_batch(
            test_db, user, TestRunBatchCreate(test_set_tag="nightly", endpoint_id=db_endpoint.id)
        )

    submit.dispatch.assert_not_called()
    left = test_db.query(TestConfiguration).filter(TestConfiguration.id.in_(calls)).count()
    assert left == 0


def test_a_refused_dispatch_fails_the_runs_not_queued_yet(
    test_db, org_sets, user, submit, db_endpoint
):
    submit.dispatch.side_effect = RuntimeError("broker down")
    with (
        patch("rhesis.backend.jobs.execution.run.update_test_run_status") as mark,
        pytest.raises(RuntimeError),
    ):
        start_batch(
            test_db, user, TestRunBatchCreate(test_set_tag="nightly", endpoint_id=db_endpoint.id)
        )

    # The first run failed inside dispatch_run; only the second is left to mark.
    assert mark.call_count == 1
    assert mark.call_args.args[2] == "Failed"


def test_the_group_needs_a_job_slot_per_run(test_db, org_sets, user, submit, db_endpoint):
    from rhesis.backend.app.services.job_capacity import JobCapacityExceededError

    with (
        patch(
            "rhesis.backend.app.services.job_capacity.get_job_limit_settings",
            return_value=MagicMock(max_active_jobs_per_org=1),
        ),
        pytest.raises(JobCapacityExceededError, match="would start 2 jobs"),
    ):
        start_batch(
            test_db, user, TestRunBatchCreate(test_set_tag="nightly", endpoint_id=db_endpoint.id)
        )
    submit.prepare.assert_not_called()


def test_a_tag_matching_one_set_is_still_a_group(test_db, org_sets, user, submit, db_endpoint):
    gamma = org_sets["gamma"]
    tag = Tag(name="weekly", organization_id=gamma.organization_id, user_id=gamma.user_id)
    test_db.add(tag)
    test_db.flush()
    test_db.add(
        TaggedItem(
            tag_id=tag.id,
            entity_id=gamma.id,
            entity_type="TestSet",
            organization_id=gamma.organization_id,
            user_id=gamma.user_id,
        )
    )
    test_db.commit()

    result = start_batch(
        test_db, user, TestRunBatchCreate(test_set_tag="weekly", endpoint_id=db_endpoint.id)
    )

    assert result["batch_id"]
    assert _configs(test_db, result)[0].attributes["batch_set_tag"] == "weekly"


def test_one_set_is_not_a_batch(test_db, org_sets, user, submit, db_endpoint):
    result = start_batch(
        test_db,
        user,
        TestRunBatchCreate(test_set_ids=[org_sets["alpha"].id], endpoint_id=db_endpoint.id),
    )

    assert result["batch_id"] is None
    assert "batch_id" not in _configs(test_db, result)[0].attributes


def test_a_set_without_the_tagged_tests_stops_the_whole_group(
    test_db, org_sets, user, submit, db_endpoint
):
    request = TestRunBatchCreate(
        test_set_tag="nightly",
        endpoint_id=db_endpoint.id,
        run_settings={"tests_tagged": ["smoke"]},
    )
    with pytest.raises(ValueError, match="No tests in beta carry the tags: smoke"):
        start_batch(test_db, user, request)
    submit.assert_not_called()


def test_an_unused_tag_is_refused(test_db, org_sets, user, submit, db_endpoint):
    with pytest.raises(ValueError, match="No test sets carry the tag: weekly"):
        start_batch(
            test_db, user, TestRunBatchCreate(test_set_tag="weekly", endpoint_id=db_endpoint.id)
        )


def test_the_quota_is_checked_once_for_every_test(test_db, org_sets, user, submit, db_endpoint):
    experiments = [{"experiment_id": str(uuid.uuid4()), "version": v} for v in ("v1", "v2")]
    with patch(
        "rhesis.backend.app.services.test_run_batch.enforce_test_execution_quota"
    ) as enforce:
        start_batch(
            test_db,
            user,
            TestRunBatchCreate(
                test_set_tag="nightly", endpoint_id=db_endpoint.id, experiments=experiments
            ),
        )
    # (alpha 2 + beta 3) tests, twice.
    assert enforce.call_args.args[-1] == 10


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"test_set_ids": [str(uuid.uuid4())], "test_set_tag": "nightly"},
        {"test_set_tag": "nightly", "run_settings": {"reference_test_run_id": str(uuid.uuid4())}},
        {"test_set_tag": "nightly", "run_settings": {"experiment_id": str(uuid.uuid4())}},
    ],
)
def test_request_needs_one_target_and_no_reuse(body):
    with pytest.raises(ValidationError):
        TestRunBatchCreate(endpoint_id=uuid.uuid4(), **body)


def test_route_starts_the_group(authenticated_client, org_sets, db_endpoint):
    with patch(
        "rhesis.backend.app.services.test_run_batch.start_batch",
        return_value={"batch_id": None, "test_set_tag": "nightly", "members": []},
    ) as start:
        response = authenticated_client.post(
            "/test_runs/batches",
            json={"test_set_tag": "nightly", "endpoint_id": str(db_endpoint.id)},
        )
    assert response.status_code == 200, response.text
    assert start.call_args.args[2].test_set_tag == "nightly"
