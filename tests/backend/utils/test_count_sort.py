"""Tests for the virtual count sorts behind the activity columns.

The annotation sort is the one with teeth: it orders the whole organization's test
runs by a count that lives two tables away, and it has to agree with the number the
grid column displays. Both halves are guarded below.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from rhesis.backend.app import models
from rhesis.backend.app.crud.annotation import (
    annotated_tests_count_expr,
    get_annotation_statistics_for_runs,
)
from rhesis.backend.app.crud.test_run import get_test_runs
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.utils.count_sort import (
    apply_virtual_count_sort,
    is_virtual_count_sort,
    model_supports_count_sort,
)
from rhesis.backend.app.utils.query_validation import validate_sort_field


def annotated_tests_count(db, test_run_id) -> int:
    """Evaluate the sort's own expression for one run."""
    return db.execute(
        select(annotated_tests_count_expr(TestRun.id)).where(TestRun.id == test_run_id)
    ).scalar()


def make_run(db, name, test_configuration, user, status, org_id) -> TestRun:
    run = TestRun(
        name=name,
        user_id=user.id,
        organization_id=uuid.UUID(str(org_id)),
        status_id=status.id,
        test_configuration_id=test_configuration.id,
        attributes={},
    )
    db.add(run)
    db.flush()
    return run


def annotate_run(
    db, run, test_configuration, user, organization, status, *, tests, annotations_per_test=1
):
    """Give *run* one result per test, each carrying some annotations."""
    annotations = []
    for _ in range(tests):
        test = Test(organization_id=organization.id, user_id=user.id)
        db.add(test)
        db.flush()
        result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=run.id,
            test_configuration_id=test_configuration.id,
            test_id=test.id,
            user_id=user.id,
            organization_id=organization.id,
            status_id=status.id,
        )
        db.add(result)
        db.flush()
        for _ in range(annotations_per_test):
            annotation = models.Annotation(
                id=uuid.uuid4(),
                entity_type="TestResult",
                entity_id=result.id,
                target_type="test_result",
                status_id=status.id,
                user_id=user.id,
                organization_id=organization.id,
            )
            db.add(annotation)
            annotations.append(annotation)
    db.flush()
    return annotations


def annotate_trace(db, run, project, user, organization, status):
    """Annotate one of the run's traces, which is not a test result."""
    now = datetime.now(timezone.utc)
    trace = models.Trace(
        trace_id=uuid.uuid4().hex,
        span_id=uuid.uuid4().hex[:16],
        project_id=project.id,
        organization_id=organization.id,
        environment="development",
        test_run_id=run.id,
        span_name="function.invoke",
        span_kind="SERVER",
        start_time=now,
        end_time=now + timedelta(seconds=1),
        duration_ms=1000.0,
        status_code="OK",
        attributes={},
        events=[],
        links=[],
        resource={},
    )
    db.add(trace)
    db.flush()
    annotation = models.Annotation(
        id=uuid.uuid4(),
        entity_type="Trace",
        entity_id=trace.id,
        target_type="trace",
        status_id=status.id,
        user_id=user.id,
        organization_id=organization.id,
    )
    db.add(annotation)
    db.flush()
    return annotation


def test_virtual_count_sort_detection():
    assert is_virtual_count_sort("comments_count")
    assert is_virtual_count_sort("tasks_count")
    assert is_virtual_count_sort("tags_count")
    assert is_virtual_count_sort("annotated_tests_count")
    assert not is_virtual_count_sort("created_at")


def test_only_the_model_test_results_point_at_can_sort_by_them():
    assert model_supports_count_sort(TestRun, "annotated_tests_count")
    assert not model_supports_count_sort(Test, "annotated_tests_count")


def test_validate_sort_field_accepts_the_annotation_count_for_runs():
    validate_sort_field(TestRun, "annotated_tests_count")


def test_validate_sort_field_rejects_the_annotation_count_elsewhere():
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Test, "annotated_tests_count")
    assert exc_info.value.status_code == 400


def test_model_supports_count_sort_for_test():
    assert model_supports_count_sort(Test, "comments_count")
    assert model_supports_count_sort(Test, "tasks_count")
    assert model_supports_count_sort(Test, "tags_count")


def test_validate_sort_field_accepts_virtual_counts():
    validate_sort_field(Test, "comments_count")
    validate_sort_field(Test, "tasks_count")
    validate_sort_field(Test, "tags_count")


def test_validate_sort_field_rejects_unknown_field():
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Test, "not_a_real_column")
    assert exc_info.value.status_code == 400


def test_apply_virtual_count_sort_builds_query(test_db):
    query = test_db.query(Test)
    sorted_query = apply_virtual_count_sort(query, Test, "comments_count", "desc")
    compiled = str(sorted_query.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "comment" in compiled.lower()
    assert "count" in compiled.lower()


def test_tag_count_subquery_excludes_soft_deleted_links(test_db):
    query = test_db.query(Test)
    sorted_query = apply_virtual_count_sort(query, Test, "tags_count", "asc")
    compiled = str(sorted_query.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at" in compiled.lower()


@pytest.mark.integration
class TestSortingRunsByAnnotationCount:
    """Ordering the whole organization's runs by how much of each was reviewed.

    A count here is not a count of annotation rows. It is how many of a run's tests
    carry at least one, which is the number the grid column shows, and it is reached
    by hopping through test_result -- annotations point at results, never at runs.
    """

    @pytest.fixture
    def annotated_runs(
        self,
        test_db,
        db_test_run,
        db_test_run_running,
        db_test_configuration,
        db_user,
        test_organization,
        db_status,
        test_org_id,
    ):
        """Three runs annotated to different depths, arranged to expose a dead sort.

        Ages are set so that neither direction of this sort is the list's created_at
        default, nor the reverse of it: newest-first gives light, heavy, none, while
        the counts give heavy, light, none. A regression where the sort quietly fell
        through to the default therefore fails both directions instead of passing one
        of them by luck.
        """
        lightly, heavily = db_test_run, db_test_run_running
        none = make_run(
            test_db, "never reviewed", db_test_configuration, db_user, db_status, test_org_id
        )
        now = datetime.now(timezone.utc)
        lightly.created_at = now
        heavily.created_at = now - timedelta(days=3)
        none.created_at = now - timedelta(days=7)
        test_db.flush()

        annotate_run(
            test_db, lightly, db_test_configuration, db_user, test_organization, db_status, tests=1
        )
        annotate_run(
            test_db, heavily, db_test_configuration, db_user, test_organization, db_status, tests=3
        )
        return str(none.id), str(lightly.id), str(heavily.id)

    def _relative(self, ordered, *ids):
        """Where the fixture's runs sit relative to each other, ignoring other rows."""
        return [run_id for run_id in ordered if run_id in ids]

    def _ordered_ids(self, db, org_id, sort_order):
        runs = get_test_runs(
            db,
            skip=0,
            limit=100,
            sort_by="annotated_tests_count",
            sort_order=sort_order,
            organization_id=org_id,
        )
        return [str(run.id) for run in runs]

    def test_orders_by_annotated_tests_descending(self, test_db, test_org_id, annotated_runs):
        none, lightly, heavily = annotated_runs

        ordered = self._ordered_ids(test_db, test_org_id, "desc")

        assert self._relative(ordered, *annotated_runs) == [heavily, lightly, none]

    def test_orders_by_annotated_tests_ascending(self, test_db, test_org_id, annotated_runs):
        none, lightly, heavily = annotated_runs

        ordered = self._ordered_ids(test_db, test_org_id, "asc")

        assert self._relative(ordered, *annotated_runs) == [none, lightly, heavily]

    def test_ascending_is_not_just_the_default_order_reversed(
        self, test_db, test_org_id, annotated_runs
    ):
        """Guards the pair above: the two directions must actually differ."""
        ascending = self._ordered_ids(test_db, test_org_id, "asc")
        descending = self._ordered_ids(test_db, test_org_id, "desc")

        assert self._relative(ascending, *annotated_runs) == list(
            reversed(self._relative(descending, *annotated_runs))
        )

    def test_neither_direction_is_the_list_s_default_order(
        self, test_db, test_org_id, annotated_runs
    ):
        """What makes the assertions above mean anything.

        If the fixture's ages happened to line up with its counts, a sort that did
        nothing at all would satisfy every ordering test here.
        """
        default = get_test_runs(test_db, skip=0, limit=100, organization_id=test_org_id)
        default_order = self._relative([str(run.id) for run in default], *annotated_runs)

        ascending = self._relative(self._ordered_ids(test_db, test_org_id, "asc"), *annotated_runs)
        descending = self._relative(
            self._ordered_ids(test_db, test_org_id, "desc"), *annotated_runs
        )

        assert default_order != ascending
        assert default_order != descending

    def test_the_sort_covers_runs_outside_the_first_page(
        self, test_db, test_org_id, annotated_runs
    ):
        """The point of sorting in the database: page one is the top of the org.

        The most annotated run is not the newest, so a sort applied to the page the
        list was handed would leave it out of a one-row page entirely -- which is
        what the second assertion pins down.
        """
        _, _, heavily = annotated_runs

        first_page = get_test_runs(
            test_db,
            skip=0,
            limit=1,
            sort_by="annotated_tests_count",
            sort_order="desc",
            organization_id=test_org_id,
        )
        default_page = get_test_runs(test_db, skip=0, limit=1, organization_id=test_org_id)

        assert [str(run.id) for run in first_page] == [heavily]
        assert [str(run.id) for run in default_page] != [heavily]

    def test_counts_tests_not_annotation_rows(
        self,
        test_db,
        test_org_id,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        db_status,
    ):
        """Five annotations spread over two tests is two, the same as the column shows."""
        annotate_run(
            test_db,
            db_test_run,
            db_test_configuration,
            db_user,
            test_organization,
            db_status,
            tests=2,
            annotations_per_test=3,
        )

        assert annotated_tests_count(test_db, db_test_run.id) == 2

    def test_annotations_on_the_run_s_traces_do_not_count(
        self,
        test_db,
        test_org_id,
        db_test_run,
        db_project,
        db_user,
        test_organization,
        db_status,
    ):
        """The column counts annotated tests, so a trace-only run reads as unreviewed.

        The Annotations tab lists trace annotations too, and its badge counts them.
        This column is a different figure on purpose; the sort has to match the column
        it sorts, not the tab.
        """
        annotate_trace(test_db, db_test_run, db_project, db_user, test_organization, db_status)

        assert annotated_tests_count(test_db, db_test_run.id) == 0

    def test_a_soft_deleted_annotation_stops_counting(
        self,
        test_db,
        test_org_id,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        db_status,
    ):
        annotations = annotate_run(
            test_db,
            db_test_run,
            db_test_configuration,
            db_user,
            test_organization,
            db_status,
            tests=2,
        )
        assert annotated_tests_count(test_db, db_test_run.id) == 2

        annotations[0].deleted_at = datetime.now(timezone.utc)
        test_db.flush()

        assert annotated_tests_count(test_db, db_test_run.id) == 1

    def test_the_sort_and_the_column_report_the_same_number(
        self,
        test_db,
        test_org_id,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        db_status,
    ):
        """The drift guard. Both read one expression; this proves they still do."""
        annotate_run(
            test_db,
            db_test_run,
            db_test_configuration,
            db_user,
            test_organization,
            db_status,
            tests=3,
            annotations_per_test=2,
        )

        displayed = get_annotation_statistics_for_runs(test_db, [db_test_run.id])
        assert (
            annotated_tests_count(test_db, db_test_run.id)
            == (displayed[str(db_test_run.id)]["annotated_tests"])
        )
