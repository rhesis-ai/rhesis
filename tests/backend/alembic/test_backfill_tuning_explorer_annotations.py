"""Pre-merge confidence tests for the tuning/explorer annotation backfill (b7d4e2f1a9c3).

TEMPORARY: delete once that migration has shipped everywhere.

Two JSONB stores move onto the ``annotation`` table, and what is worth pinning is
what each one becomes: a tuning review becomes a judgement targeting the metric
by id with the verdict it judged in ``attributes``, and a human explorer label
becomes an entity-level annotation whose status carries the verdict. The label
strip is the only destructive step, so the case that matters most is
``test_a_label_it_could_not_attribute_keeps_its_metadata`` — a row the insert
skipped must not come out of this with no label at all.

Drives ``upgrade()``/``downgrade()`` directly against the ``test_db`` connection
inside an ``Operations.context``, so everything rolls back at teardown.
"""

import importlib.util
import json
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

RHESIS_SKIP_MIGRATIONS = os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in (
    "1",
    "true",
    "yes",
)

pytestmark = pytest.mark.skipif(
    RHESIS_SKIP_MIGRATIONS,
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_MIGRATION_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "alembic"
    / "versions"
    / "b7d4e2f1a9c3_backfill_tuning_and_explorer_annotations.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "tuning_explorer_backfill_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()

REJECTION_COMMENT = "scored a pass, but this is plainly an insult"
REVIEWED_AT = "2026-08-20T09:00:00+00:00"


@pytest.fixture
def migration_ops(test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


def _rebind_org(conn, org_id) -> None:
    """Put the tenant GUC back after the migration walked every organization.

    ``upgrade()`` leaves it pointing at whichever org it saw last, and the reads
    these tests do afterwards are RLS-filtered like any other.
    """
    conn.execute(
        sa.text(
            "SELECT set_config('app.current_organization', :org_id, true),"
            "       set_config('app.current_project', '', true)"
        ),
        {"org_id": str(org_id)},
    )


def _insert_metric(conn, org_id, user_id) -> uuid.UUID:
    return conn.execute(
        sa.text(
            """
            INSERT INTO metric (
                name, evaluation_prompt, score_type, metric_scope, organization_id, user_id
            )
            VALUES (
                :name, 'Score how toxic the answer is.', 'binary',
                CAST('["single_turn"]' AS jsonb),
                CAST(:org_id AS uuid), CAST(:user_id AS uuid)
            )
            RETURNING id
            """
        ),
        {"name": f"Backfill Metric {uuid.uuid4().hex[:8]}", "org_id": org_id, "user_id": user_id},
    ).scalar()


def _insert_test(conn, *, org_id, user_id, metadata, metric_id=None) -> uuid.UUID:
    return conn.execute(
        sa.text(
            """
            INSERT INTO test (organization_id, user_id, metric_id, test_metadata)
            VALUES (
                CAST(:org_id AS uuid), CAST(:user_id AS uuid),
                CAST(:metric_id AS uuid), CAST(:metadata AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "org_id": org_id,
            "user_id": None if user_id is None else str(user_id),
            "metric_id": None if metric_id is None else str(metric_id),
            "metadata": json.dumps(metadata),
        },
    ).scalar()


def _review(decision: str, reviewer_id, *, comment=None, verdict="pass") -> dict:
    return {
        "decision": decision,
        "comment": comment,
        "verdict": verdict,
        "score_type": "binary",
        "reviewer_id": str(reviewer_id),
        "reviewed_at": REVIEWED_AT,
    }


def _annotate_entity_level(conn, test_id, org_id, user_id, status_name: str) -> None:
    """Write an entity-level label the way ``explorer/labels.set_label`` does.

    Pass and Fail live under the ``TestResult`` entity type, which is where every
    organization already has them.
    """
    conn.execute(
        sa.text(
            """
            INSERT INTO annotation (
                organization_id, user_id, entity_type, entity_id, target_type, status_id
            )
            SELECT CAST(:org_id AS uuid), CAST(:user_id AS uuid), 'Test',
                   CAST(:test_id AS uuid), 'test', s.id
            FROM status s
            JOIN type_lookup tl ON tl.id = s.entity_type_id
            WHERE s.organization_id = CAST(:org_id AS uuid)
              AND tl.type_name = 'EntityType'
              AND tl.type_value = 'TestResult'
              AND s.name = :status_name
            """
        ),
        {
            "org_id": str(org_id),
            "user_id": str(user_id),
            "test_id": str(test_id),
            "status_name": status_name,
        },
    )


def _annotations_on(conn, test_id) -> list:
    rows = conn.execute(
        sa.text(
            """
            SELECT a.target_type, a.target_reference, s.name, a.comments, a.attributes,
                   a.user_id, a.created_at
            FROM annotation a
            JOIN status s ON s.id = a.status_id
            WHERE a.entity_type = 'Test'
              AND a.entity_id = CAST(:test_id AS uuid)
              AND a.deleted_at IS NULL
            ORDER BY s.name
            """
        ),
        {"test_id": str(test_id)},
    ).fetchall()
    return [tuple(row) for row in rows]


def _metadata_of(conn, test_id) -> dict:
    raw = conn.execute(
        sa.text("SELECT test_metadata FROM test WHERE id = CAST(:id AS uuid)"),
        {"id": str(test_id)},
    ).scalar()
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


@pytest.mark.integration
class TestTheStatusSeed:
    def test_accepted_and_rejected_exist_for_the_org(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """Every later judgement resolves its status by name, so the pair has to
        be there before any of them can be written."""
        conn = test_db.connection()

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        names = conn.execute(
            sa.text(
                """
                SELECT s.name FROM status s
                JOIN type_lookup tl ON tl.id = s.entity_type_id
                WHERE tl.type_name = 'EntityType' AND tl.type_value = 'Annotation'
                  AND s.organization_id = CAST(:org_id AS uuid)
                ORDER BY s.name
                """
            ),
            {"org_id": test_org_id},
        ).scalars()
        assert list(names) == ["Accepted", "Rejected"]


@pytest.mark.integration
class TestTuningJudgements:
    def test_each_review_becomes_a_judgement_targeting_the_metric(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        metric_id = _insert_metric(conn, test_org_id, authenticated_user_id)
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metric_id=metric_id,
            metadata={
                "result": {"verdict": "pass", "reasoning": "reads as polite"},
                "reviews": [
                    _review("accepted", authenticated_user_id),
                    _review("rejected", authenticated_user_id, comment=REJECTION_COMMENT),
                ],
            },
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        stored = _annotations_on(conn, case_id)
        assert len(stored) == 2
        accepted, rejected = stored
        assert accepted[:4] == ("metric", str(metric_id), "Accepted", None)
        assert rejected[:4] == ("metric", str(metric_id), "Rejected", REJECTION_COMMENT)
        # The verdict each one judged, which only tuning re-reads.
        assert accepted[4] == {"verdict": "pass", "score_type": "binary"}
        assert str(accepted[5]) == str(authenticated_user_id)

    def test_the_reviews_array_is_left_in_place(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """PR-5 is what clears it. Until then it is the only record of anything
        this migration failed to copy."""
        conn = test_db.connection()
        metric_id = _insert_metric(conn, test_org_id, authenticated_user_id)
        reviews = [_review("rejected", authenticated_user_id, comment=REJECTION_COMMENT)]
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metric_id=metric_id,
            metadata={"reviews": reviews},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _metadata_of(conn, case_id)["reviews"] == reviews

    def test_a_review_by_an_unknown_author_is_skipped_rather_than_aborting(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """A foreign key that no longer resolves must not take the migration down
        with it."""
        conn = test_db.connection()
        metric_id = _insert_metric(conn, test_org_id, authenticated_user_id)
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metric_id=metric_id,
            metadata={
                "reviews": [
                    _review("rejected", uuid.uuid4(), comment="written by a deleted user"),
                    _review("accepted", authenticated_user_id),
                ]
            },
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        stored = _annotations_on(conn, case_id)
        assert [row[2] for row in stored] == ["Accepted"]

    def test_a_test_that_is_not_a_tuning_case_is_not_touched(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """``metric_id`` is what makes a row a tuning case, so a plain test with a
        stray ``reviews`` key is left alone."""
        conn = test_db.connection()
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"reviews": [_review("accepted", authenticated_user_id)]},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _annotations_on(conn, case_id) == []


@pytest.mark.integration
class TestExplorerLabels:
    def test_a_human_label_becomes_an_annotation_and_the_pair_is_stripped(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"label": "pass", "labeler": "user", "output": "An answer", "model_score": 0},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        stored = _annotations_on(conn, test_id)
        assert len(stored) == 1
        assert stored[0][:4] == ("test", None, "Pass", None)
        assert str(stored[0][5]) == str(authenticated_user_id)
        # The label moved rather than being copied, and everything else survives.
        metadata = _metadata_of(conn, test_id)
        assert "label" not in metadata
        assert "labeler" not in metadata
        assert metadata["output"] == "An answer"

    def test_a_fail_label_becomes_the_fail_status(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"label": "fail", "labeler": "user"},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert [row[2] for row in _annotations_on(conn, test_id)] == ["Fail"]

    def test_a_metrics_own_label_stays_exactly_where_it_is(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """Whether the metric agrees with a person is the thing the split exists
        to express, so the metric's verdict is not a judgement to migrate."""
        conn = test_db.connection()
        metadata = {"label": "fail", "labeler": "answer_relevancy", "model_score": 0.3}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=metadata
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _annotations_on(conn, test_id) == []
        assert _metadata_of(conn, test_id) == metadata

    def test_a_topic_marker_is_not_a_label(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        metadata = {"label": "topic_marker", "labeler": "user", "output": ""}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=metadata
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _annotations_on(conn, test_id) == []
        assert _metadata_of(conn, test_id) == metadata

    def test_a_label_it_could_not_attribute_keeps_its_metadata(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """The strip is guarded on the annotation having landed. Without that
        guard a row with no author would come out of this with no label at all."""
        conn = test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=None,
            metadata={"label": "pass", "labeler": "user"},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _annotations_on(conn, test_id) == []
        assert _metadata_of(conn, test_id) == {"label": "pass", "labeler": "user"}


@pytest.mark.integration
class TestRoundTrip:
    def test_upgrade_is_idempotent(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """Re-running must not double every judgement — there are no stored ids to
        conflict on, so the guard is a natural key."""
        conn = test_db.connection()
        metric_id = _insert_metric(conn, test_org_id, authenticated_user_id)
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metric_id=metric_id,
            metadata={
                "reviews": [
                    _review("accepted", authenticated_user_id),
                    _review("rejected", authenticated_user_id, comment=REJECTION_COMMENT),
                ]
            },
        )
        labelled_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"label": "pass", "labeler": "user"},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)
        after_first = (_annotations_on(conn, case_id), _annotations_on(conn, labelled_id))

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert (_annotations_on(conn, case_id), _annotations_on(conn, labelled_id)) == after_first

    def test_downgrade_puts_the_explorer_label_back(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        before = {"label": "fail", "labeler": "user", "output": "An answer"}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=before
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)
        _migration.downgrade()
        _rebind_org(conn, test_org_id)

        assert _metadata_of(conn, test_id) == before
        assert _annotations_on(conn, test_id) == []

    def test_downgrade_removes_the_tuning_judgements(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        metric_id = _insert_metric(conn, test_org_id, authenticated_user_id)
        case_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metric_id=metric_id,
            metadata={"reviews": [_review("rejected", authenticated_user_id, comment="no")]},
        )

        _migration.upgrade()
        _rebind_org(conn, test_org_id)
        _migration.downgrade()
        _rebind_org(conn, test_org_id)

        assert _annotations_on(conn, case_id) == []

    def test_downgrade_leaves_a_metrics_own_label_alone(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """The restore writes with ``||``, which overwrites keys.

        A test the upgrade deliberately left alone still carries the metric's
        verdict in its metadata. Without the ``label IS NULL`` guard the restore
        would overwrite it with a person's and relabel the metric's work as
        theirs -- a downgrade destroying data the upgrade never touched.
        """
        conn = test_db.connection()
        metric_label = {"label": "fail", "labeler": "Toxicity", "output": "An answer"}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=metric_label
        )
        _annotate_entity_level(conn, test_id, test_org_id, authenticated_user_id, "Pass")

        _migration.upgrade()
        _rebind_org(conn, test_org_id)
        _migration.downgrade()
        _rebind_org(conn, test_org_id)

        assert _metadata_of(conn, test_id) == metric_label


@pytest.mark.integration
class TestARollingDeploy:
    """The new code can be writing labels before this migration runs.

    Both cases below have an annotation already present for the same author, so
    the insert skips the row as a duplicate. What the strip does then is the
    whole question: strip regardless and the metadata verdict is gone.
    """

    def test_a_label_is_kept_when_the_existing_annotation_disagrees(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        before = {"label": "fail", "labeler": "user", "output": "An answer"}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=before
        )
        # The person has since changed their mind through the new code path.
        _annotate_entity_level(conn, test_id, test_org_id, authenticated_user_id, "Pass")

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        # Exactly one annotation: the migration added none, because one was there.
        assert [row[2] for row in _annotations_on(conn, test_id)] == ["Pass"]
        # And the older verdict survives rather than being silently dropped.
        assert _metadata_of(conn, test_id) == before

    def test_a_label_is_stripped_when_the_existing_annotation_agrees(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"label": "pass", "labeler": "user", "output": "An answer"},
        )
        _annotate_entity_level(conn, test_id, test_org_id, authenticated_user_id, "Pass")

        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        # The verdict is represented by the annotation, so the pair is redundant.
        assert [row[2] for row in _annotations_on(conn, test_id)] == ["Pass"]
        assert _metadata_of(conn, test_id) == {"output": "An answer"}
