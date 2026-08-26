"""The test_result.execution/verdict schema: the migration's backfill
mapping and the CHECK constraints that make the (execution, verdict)
invariant unbreakable at the database level, not just by convention.
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "apps/backend/src/rhesis/backend/alembic/versions"
    / "ff71b040aebf_add_test_result_execution_verdict.py"
)


def _load_migration():
    """Import the migration module for its _PASSED_NAMES/_FAILED_NAMES
    constants, so this test cannot silently drift from the SQL that
    actually ran -- it exercises the same literals, not a hand-copied
    approximation of them.
    """
    spec = importlib.util.spec_from_file_location("_backfill_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration()


@pytest.mark.unit
class TestBackfillMapping:
    """Runs the migration's exact CASE expressions against a bound status
    name, with no database row required -- this is the SQL logic itself,
    not an integration test of the upgrade path (that already ran once,
    for real, to build every other test's schema in this suite).
    """

    @pytest.mark.parametrize(
        "status_name,expected_execution,expected_verdict",
        [
            ("Pass", "ok", "pass"),
            ("Passed", "ok", "pass"),
            ("Completed", "ok", "pass"),
            ("Complete", "ok", "pass"),
            ("Success", "ok", "pass"),
            ("Successful", "ok", "pass"),
            ("Finished", "ok", "pass"),
            ("Done", "ok", "pass"),
            ("Fail", "ok", "fail"),
            ("Failed", "ok", "fail"),
            ("Error", "error", None),
            # Neither passed/failed synonym nor 'error' -- not_run, same as
            # a row with no status at all. Covers the pre-fix ERROR-bucket
            # members (Aborted, Cancelled, Pending, Review) deliberately:
            # the migration does not try to distinguish them retroactively.
            ("Pending", "not_run", None),
            ("Review", "not_run", None),
            ("Aborted", "not_run", None),
            ("Cancelled", "not_run", None),
            ("Some Unrecognized Legacy Name", "not_run", None),
        ],
    )
    def test_maps_status_name_to_execution_and_verdict(
        self, test_db: Session, status_name, expected_execution, expected_verdict
    ):
        row = test_db.execute(
            text(
                f"""
                SELECT
                    CASE
                        WHEN lower(:name) = ANY (ARRAY[{_migration._PASSED_NAMES}]) THEN 'ok'
                        WHEN lower(:name) = ANY (ARRAY[{_migration._FAILED_NAMES}]) THEN 'ok'
                        WHEN lower(:name) = 'error' THEN 'error'
                        ELSE 'not_run'
                    END,
                    CASE
                        WHEN lower(:name) = ANY (ARRAY[{_migration._PASSED_NAMES}]) THEN 'pass'
                        WHEN lower(:name) = ANY (ARRAY[{_migration._FAILED_NAMES}]) THEN 'fail'
                        ELSE NULL
                    END
                """
            ),
            {"name": status_name},
        ).one()
        assert row[0] == expected_execution
        assert row[1] == expected_verdict


@pytest.mark.unit
class TestExecutionVerdictConstraints:
    """The CHECK constraints, exercised with a bare INSERT so a violation
    surfaces as a database error regardless of what ORM-layer validation
    does or doesn't catch.
    """

    def _insert(self, db: Session, org_id, user_id, *, execution: str, verdict) -> None:
        db.execute(
            text(
                """
                INSERT INTO test_result
                    (id, organization_id, user_id, execution, verdict, nano_id)
                VALUES
                    (gen_random_uuid(), :org_id, :user_id, :execution, :verdict,
                     substr(md5(random()::text), 1, 12))
                """
            ),
            {
                "org_id": str(org_id),
                "user_id": str(user_id),
                "execution": execution,
                "verdict": verdict,
            },
        )
        db.flush()

    def test_ok_without_verdict_is_rejected(self, test_db: Session, test_organization, db_user):
        with pytest.raises(IntegrityError, match="ck_test_result_verdict_requires_ok"):
            self._insert(test_db, test_organization.id, db_user.id, execution="ok", verdict=None)
        test_db.rollback()

    def test_error_with_a_verdict_is_rejected(self, test_db: Session, test_organization, db_user):
        """A verdict on an errored test is not stale data to tolerate -- it
        means some caller mixed up the two axes.
        """
        with pytest.raises(IntegrityError, match="ck_test_result_verdict_requires_ok"):
            self._insert(
                test_db, test_organization.id, db_user.id, execution="error", verdict="pass"
            )
        test_db.rollback()

    def test_unknown_execution_value_is_rejected(
        self, test_db: Session, test_organization, db_user
    ):
        with pytest.raises(IntegrityError, match="ck_test_result_execution"):
            self._insert(
                test_db, test_organization.id, db_user.id, execution="sideways", verdict=None
            )
        test_db.rollback()

    def test_unknown_verdict_value_is_rejected(self, test_db: Session, test_organization, db_user):
        with pytest.raises(IntegrityError, match="ck_test_result_verdict"):
            self._insert(test_db, test_organization.id, db_user.id, execution="ok", verdict="maybe")
        test_db.rollback()

    def test_ok_with_each_verdict_is_accepted(self, test_db: Session, test_organization, db_user):
        for verdict in ("pass", "fail", "inconclusive"):
            self._insert(test_db, test_organization.id, db_user.id, execution="ok", verdict=verdict)
        test_db.rollback()

    def test_non_ok_without_verdict_is_accepted(self, test_db: Session, test_organization, db_user):
        for execution in ("not_run", "running", "error", "cancelled"):
            self._insert(
                test_db, test_organization.id, db_user.id, execution=execution, verdict=None
            )
        test_db.rollback()


@pytest.mark.unit
class TestReviewStatusRemoved:
    def test_seeded_review_test_result_status_is_gone(self, test_db: Session):
        """Never written by any code path (inventory.md bug 7); seeding it
        for new orgs only kept the drift alive.
        """
        row = test_db.execute(
            text(
                """
                SELECT count(*) FROM status s
                JOIN type_lookup tl ON s.entity_type_id = tl.id
                WHERE tl.type_name = 'EntityType'
                  AND tl.type_value = 'TestResult'
                  AND lower(s.name) = 'review'
                """
            )
        ).scalar()
        assert row == 0
