"""rename_behavior_to_requirement

Single atomic cutover of the Behavior entity to Requirement: table, columns,
constraints, indexes, the three stats views, the delete-user procedure, and
every stored value that names the entity by string. Entity *instance* values
(Reliability, Robustness, Compliance, ...) are NOT touched.

RLS: nothing to do. Both `tenant_isolation` and `project_isolation` policies
on behavior/behavior_metric are the generic, OID-attached pair with no
"behavior" in their name or qual/with_check text -- they follow the table
rename automatically.

Revision ID: 491519fd3010
Revises: b857edcac3c0
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "491519fd3010"
down_revision: Union[str, None] = "b857edcac3c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -- View DDL -----------------------------------------------------------
# CREATE OR REPLACE VIEW cannot rename an existing output column, so these
# three (the ones that select behavior_id/behavior_name) need DROP + CREATE.
# v_test_run_stats has no behavior reference and is left alone.

V_TEST_RESULT_STATS = """
CREATE VIEW v_test_result_stats AS
SELECT trs.id AS test_result_id,
    trs.organization_id,
    trs.created_at,
    trs.test_run_id,
    trs.test_id,
    trs.test_metrics,
    s.name AS status_name,
    CASE
        WHEN lower(s.name) = ANY (ARRAY['complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful']) THEN 'passed'
        WHEN lower(s.name) = ANY (ARRAY['fail', 'failed']) THEN 'failed'
        ELSE 'pending'
    END AS result,
    t.status_id AS test_status_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.test_type_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    tr.id AS run_id,
    tr.name AS test_run_name,
    tr.created_at AS test_run_created_at,
    EXTRACT(year FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS year,
    EXTRACT(month FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS month
FROM test_result trs
JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""

V_TEST_STATS = """
CREATE VIEW v_test_stats AS
WITH results AS (
    SELECT trs.test_id,
        trs.created_at,
        CASE
            WHEN lower(s.name) = ANY (ARRAY['complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful']) THEN 'passed'
            WHEN lower(s.name) = ANY (ARRAY['fail', 'failed']) THEN 'failed'
            ELSE 'pending'
        END AS result
    FROM test_result trs
    JOIN status s ON trs.status_id = s.id
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result = 'pending') AS pending_count,
        max(results.created_at) AS last_run_at
    FROM results
    GROUP BY results.test_id
)
SELECT t.id AS test_id,
    t.organization_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.test_type_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.status_id AS test_status_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    t.created_at,
    EXTRACT(year FROM t.created_at)::integer AS year,
    EXTRACT(month FROM t.created_at)::integer AS month,
    COALESCE(agg.run_count, 0::bigint) AS run_count,
    COALESCE(agg.passed_count, 0::bigint) AS passed_count,
    COALESCE(agg.failed_count, 0::bigint) AS failed_count,
    COALESCE(agg.pending_count, 0::bigint) AS pending_count,
    agg.run_count IS NULL OR agg.run_count = 0 AS is_unrun,
    agg.last_run_at
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
WHERE t.deleted_at IS NULL
"""

V_METRIC_STATS = """
CREATE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT trs.id AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.requirement_id,
        trs.created_at,
        EXTRACT(year FROM trs.created_at)::integer AS year,
        EXTRACT(month FROM trs.created_at)::integer AS month,
        CASE
            WHEN lower(s.name) = ANY (ARRAY['complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful']) THEN 'passed'
            WHEN lower(s.name) = ANY (ARRAY['fail', 'failed']) THEN 'failed'
            ELSE 'pending'
        END AS overall_result,
        m.key AS metric_name,
        (m.value ->> 'is_successful')::boolean AS is_successful,
        m.value ? 'override' AND (m.value -> 'override') <> 'null'::jsonb AND (m.value -> 'override') <> '{}'::jsonb AS has_override,
        m.value #>> '{override,original_value}' AS override_original_value_raw
    FROM test_result trs
    JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
    JOIN status s ON trs.status_id = s.id
    CROSS JOIN LATERAL jsonb_each(trs.test_metrics -> 'metrics') m(key, value)
    WHERE trs.deleted_at IS NULL AND m.value ? 'is_successful'
)
SELECT test_result_id,
    organization_id,
    test_run_id,
    test_id,
    requirement_id,
    created_at,
    year,
    month,
    metric_name,
    has_override,
    COALESCE(override_original_value_raw::boolean, is_successful) AS automated_success,
    CASE
        WHEN has_override THEN is_successful
        WHEN overall_result = 'passed' AND NOT is_successful THEN true
        WHEN overall_result = 'failed' AND is_successful THEN false
        ELSE is_successful
    END AS effective_success
FROM unnested
"""

DROP_VIEWS = """
DROP VIEW v_test_result_stats;
DROP VIEW v_test_stats;
DROP VIEW v_metric_stats;
"""

# -- Procedure DDL --------------------------------------------------------
# CREATE OR REPLACE PROCEDURE keeps the object's OID, so the existing
# COMMENT ON PROCEDURE survives untouched -- no need to reissue it.
#
# Also drops a pre-existing, unrelated bug while this body is being rewritten
# anyway: `DELETE FROM response_pattern` referenced a table dropped by PR
# #2435, well before this rename. Left in place it means every org deletion
# has been failing at runtime since that PR merged.

DELETE_USER_PROCEDURE = """
CREATE OR REPLACE PROCEDURE delete_user_and_organization_data(target_email text)
LANGUAGE plpgsql
AS $$
DECLARE
    target_user_id UUID;
    org_ids UUID[];
BEGIN
    -- Step 1: Get the user ID
    SELECT id INTO target_user_id FROM "user" WHERE email = target_email;

    IF target_user_id IS NULL THEN
        RAISE NOTICE 'User not found, exiting.';
        RETURN;
    END IF;

    -- Step 2: Collect organization IDs
    SELECT ARRAY_AGG(id) INTO org_ids
    FROM organization
    WHERE user_id = target_user_id OR owner_id = target_user_id;

    -- Step 3: Delete all org-related data
    IF org_ids IS NOT NULL AND array_length(org_ids, 1) IS NOT NULL THEN

        -- Delete other users in those organizations
        DELETE FROM "user"
        WHERE organization_id = ANY(org_ids)
          AND id <> target_user_id;

        -- Detach the target user from any org
        UPDATE "user"
        SET organization_id = NULL
        WHERE id = target_user_id;

        -- Delete dependent entities
        DELETE FROM test_result
        WHERE test_configuration_id IN (
            SELECT id FROM test_configuration
            WHERE organization_id = ANY(org_ids)
        );

        DELETE FROM test_run
        WHERE test_configuration_id IN (
            SELECT id FROM test_configuration
            WHERE organization_id = ANY(org_ids)
        );

        DELETE FROM test_configuration WHERE organization_id = ANY(org_ids);
        DELETE FROM test_test_set WHERE test_set_id IN (SELECT id FROM test_set WHERE organization_id = ANY(org_ids));
        DELETE FROM test_context WHERE test_id IN (SELECT id FROM test WHERE organization_id = ANY(org_ids));
        DELETE FROM test WHERE organization_id = ANY(org_ids);
        DELETE FROM test_set WHERE organization_id = ANY(org_ids);
        DELETE FROM endpoint WHERE project_id IN (SELECT id FROM project WHERE organization_id = ANY(org_ids));
        DELETE FROM endpoint WHERE organization_id = ANY(org_ids);
        DELETE FROM project WHERE organization_id = ANY(org_ids);
        DELETE FROM prompt_use_case WHERE organization_id = ANY(org_ids);
        DELETE FROM prompt WHERE organization_id = ANY(org_ids);
        DELETE FROM prompt_template WHERE organization_id = ANY(org_ids);
        DELETE FROM risk_use_case WHERE organization_id = ANY(org_ids);
        DELETE FROM risk WHERE organization_id = ANY(org_ids);
        DELETE FROM use_case WHERE organization_id = ANY(org_ids);
        DELETE FROM requirement_metric WHERE organization_id = ANY(org_ids);
        DELETE FROM requirement WHERE organization_id = ANY(org_ids);
        DELETE FROM category WHERE organization_id = ANY(org_ids);
        DELETE FROM demographic WHERE organization_id = ANY(org_ids);
        DELETE FROM dimension WHERE organization_id = ANY(org_ids);
        DELETE FROM topic WHERE organization_id = ANY(org_ids);
        DELETE FROM subscription WHERE organization_id = ANY(org_ids);
        DELETE FROM metric WHERE organization_id = ANY(org_ids);
        DELETE FROM status WHERE organization_id = ANY(org_ids);
        DELETE FROM token WHERE organization_id = ANY(org_ids);
        DELETE FROM type_lookup WHERE organization_id = ANY(org_ids);
        DELETE FROM tagged_item WHERE organization_id = ANY(org_ids);
        DELETE FROM tag WHERE organization_id = ANY(org_ids);

        UPDATE organization
        SET is_onboarding_complete = false,
            user_id = NULL,
            owner_id = NULL
        WHERE id = ANY(org_ids);

        -- Finally, delete the organizations
        DELETE FROM organization WHERE id = ANY(org_ids);
    END IF;

    -- Step 4: Clean up test runs owned by this user
    DELETE FROM test_run WHERE user_id = target_user_id;

    -- Step 5: Delete the user itself
    DELETE FROM "user" WHERE id = target_user_id;

    RAISE NOTICE 'User % and all related data have been deleted', target_email;
END;
$$
"""

# -- Backfills -------------------------------------------------------------
# Idempotent, guarded on the old value/key, so a re-run after a partial
# failure is safe. Per-org-count row-level assertions live in the
# verification gates, not here.

BACKFILL_TYPE_LOOKUP = """
UPDATE type_lookup
SET type_value = 'Requirement', description = 'Entity type for requirements'
WHERE type_value = 'Behavior'
"""

# UPDATE in place, never delete+insert: custom roles have role_permission
# rows keyed on permission.id, and recreating the row orphans every custom
# grant.
BACKFILL_PERMISSION = """
UPDATE permission
SET name = REPLACE(name, 'behavior:', 'requirement:'),
    display_name = REPLACE(display_name, 'behavior', 'requirement'),
    resource_type = 'requirement'
WHERE resource_type = 'behavior'
"""

# Six polymorphic entity_type columns (models/mixins.py's EntityMixin).
BACKFILL_ENTITY_TYPE_TABLES = (
    "tagged_item",
    "comment",
    "file",
    "task",
    "embedding",
    "notification",
)

BACKFILL_TEST_CONFIGURATION = """
UPDATE test_configuration
SET attributes = jsonb_set(attributes, '{metrics_source}', '"requirement"')
WHERE attributes ->> 'metrics_source' = 'behavior'
"""

# test_set.attributes carries the entity twice: a top-level UUID array and a
# name array nested under metadata (both populated by the SDK synthesizer).
BACKFILL_TEST_SET_ATTRIBUTES_TOP = """
UPDATE test_set
SET attributes = (attributes - 'behaviors') || jsonb_build_object('requirements', attributes -> 'behaviors')
WHERE attributes ? 'behaviors'
"""

BACKFILL_TEST_SET_ATTRIBUTES_METADATA = """
UPDATE test_set
SET attributes = jsonb_set(
    attributes,
    '{metadata}',
    ((attributes -> 'metadata')::jsonb - 'behaviors')
        || jsonb_build_object('requirements', attributes -> 'metadata' -> 'behaviors')
)
WHERE attributes -> 'metadata' ? 'behaviors'
"""

# architect_session.plan_data has three independent shapes to migrate:
# a top-level list, a top-level mapping list (with a nested per-element key),
# and a per-element key nested inside the test_sets array.
BACKFILL_PLAN_DATA_BEHAVIORS = """
UPDATE architect_session
SET plan_data = (plan_data - 'behaviors') || jsonb_build_object('requirements', plan_data -> 'behaviors')
WHERE plan_data ? 'behaviors'
"""

BACKFILL_PLAN_DATA_MAPPINGS = """
UPDATE architect_session
SET plan_data = (plan_data - 'behavior_metric_mappings') || jsonb_build_object(
    'requirement_metric_mappings',
    (
        SELECT jsonb_agg(
            CASE WHEN elem ? 'behavior'
                 THEN (elem - 'behavior') || jsonb_build_object('requirement', elem -> 'behavior')
                 ELSE elem
            END
        )
        FROM jsonb_array_elements(plan_data -> 'behavior_metric_mappings') elem
    )
)
WHERE plan_data ? 'behavior_metric_mappings'
"""

BACKFILL_PLAN_DATA_TEST_SETS = """
UPDATE architect_session
SET plan_data = jsonb_set(
    plan_data,
    '{test_sets}',
    (
        SELECT jsonb_agg(
            CASE WHEN elem ? 'behaviors'
                 THEN (elem - 'behaviors') || jsonb_build_object('requirements', elem -> 'behaviors')
                 ELSE elem
            END
        )
        FROM jsonb_array_elements(COALESCE(plan_data -> 'test_sets', '[]'::jsonb)) elem
    )
)
WHERE EXISTS (
    SELECT 1 FROM jsonb_array_elements(COALESCE(plan_data -> 'test_sets', '[]'::jsonb)) elem
    WHERE elem ? 'behaviors'
)
"""


def upgrade() -> None:
    # 1. Tables
    op.rename_table("behavior", "requirement")
    op.rename_table("behavior_metric", "requirement_metric")

    # 2. Columns
    op.alter_column("requirement_metric", "behavior_id", new_column_name="requirement_id")
    op.alter_column("test", "behavior_id", new_column_name="requirement_id")
    op.alter_column("prompt", "behavior_id", new_column_name="requirement_id")

    # 3. Constraints -- names never follow a table rename.
    op.execute("ALTER TABLE requirement RENAME CONSTRAINT behavior_pkey TO requirement_pkey")
    op.execute(
        "ALTER TABLE requirement RENAME CONSTRAINT behavior_organization_id_fkey "
        "TO requirement_organization_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement RENAME CONSTRAINT behavior_project_id_fkey "
        "TO requirement_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement RENAME CONSTRAINT behavior_status_id_fkey "
        "TO requirement_status_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement RENAME CONSTRAINT behavior_user_id_fkey "
        "TO requirement_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement RENAME CONSTRAINT uq_behavior_nano_id TO uq_requirement_nano_id"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_pkey "
        "TO requirement_metric_pkey"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_behavior_id_fkey "
        "TO requirement_metric_requirement_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_metric_id_fkey "
        "TO requirement_metric_metric_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_organization_id_fkey "
        "TO requirement_metric_organization_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_project_id_fkey "
        "TO requirement_metric_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE requirement_metric RENAME CONSTRAINT behavior_metric_user_id_fkey "
        "TO requirement_metric_user_id_fkey"
    )
    # These two sit on non-requirement tables -- easy to miss.
    op.execute(
        "ALTER TABLE prompt RENAME CONSTRAINT prompt_behavior_id_fkey TO prompt_requirement_id_fkey"
    )
    op.execute(
        "ALTER TABLE test RENAME CONSTRAINT test_behavior_id_fkey TO test_requirement_id_fkey"
    )

    # 4. Standalone indexes. The other 3 (behavior_pkey, behavior_metric_pkey,
    # uq_behavior_nano_id) are constraint-backed and were already renamed by
    # step 3 -- renaming them again here would error on an already-renamed name.
    op.execute("ALTER INDEX ix_behavior_deleted_at RENAME TO ix_requirement_deleted_at")
    op.execute("ALTER INDEX ix_behavior_id RENAME TO ix_requirement_id")
    op.execute("ALTER INDEX ix_behavior_project_id RENAME TO ix_requirement_project_id")
    op.execute("ALTER INDEX ix_test_behavior_id RENAME TO ix_test_requirement_id")

    # 5. Stats views -- output column names are physical and don't follow a
    # base-table rename, so these need DROP + CREATE, not CREATE OR REPLACE.
    op.execute(DROP_VIEWS)
    op.execute(V_TEST_RESULT_STATS)
    op.execute(V_TEST_STATS)
    op.execute(V_METRIC_STATS)

    # 6. delete_user_and_organization_data procedure
    op.execute(DELETE_USER_PROCEDURE)

    # 7. RLS: nothing to do -- see module docstring.

    # 8. Backfills
    op.execute(BACKFILL_TYPE_LOOKUP)
    op.execute(BACKFILL_PERMISSION)
    for table in BACKFILL_ENTITY_TYPE_TABLES:
        op.execute(
            f"UPDATE {table} SET entity_type = 'Requirement' WHERE entity_type = 'Behavior'"
        )
    op.execute(BACKFILL_TEST_CONFIGURATION)
    op.execute(BACKFILL_TEST_SET_ATTRIBUTES_TOP)
    op.execute(BACKFILL_TEST_SET_ATTRIBUTES_METADATA)
    op.execute(BACKFILL_PLAN_DATA_BEHAVIORS)
    op.execute(BACKFILL_PLAN_DATA_MAPPINGS)
    op.execute(BACKFILL_PLAN_DATA_TEST_SETS)


def downgrade() -> None:
    # Not implemented: per team decision, this cutover has no tested
    # downgrade path given the platform's current user count. Rollback is a
    # snapshot restore, not `alembic downgrade`.
    raise NotImplementedError(
        "491519fd3010 has no downgrade -- restore from a pre-migration snapshot instead"
    )
