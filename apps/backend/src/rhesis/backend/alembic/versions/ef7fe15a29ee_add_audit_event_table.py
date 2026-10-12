"""Add the append-only audit_event table

The store for the Enterprise audit log. Nothing writes to it yet.

Append-only, enforced twice:

- Every role that got privileges on the new table (CNPG's default privileges
  give the app role SELECT, INSERT, UPDATE and DELETE) loses UPDATE, DELETE
  and TRUNCATE. Roles are found from the table's ACL rather than named,
  because the app role is ``rhesis-user`` in production and ``rhesis-app`` in
  the test suite.
- A statement trigger raises on UPDATE, DELETE and TRUNCATE. It covers what
  REVOKE cannot: locally the app is a superuser, and a single-role self-hosted
  install runs the app as the table owner.

The only delete path is ``audit_event_purge()``, a SECURITY DEFINER function
for the retention job. It marks its own transaction so the trigger lets that
DELETE through, and it records an ``audit_log.purged`` row with the count. It
cuts on ``recorded_at``, the window later integrity checkpoints seal.

``recorded_at`` is set by a trigger to ``clock_timestamp()``, so a caller
cannot backdate a row into a window that has already been sealed. ``id``
defaults to a UUIDv7, so ids sort by time.

No foreign keys. Deleting an org, project, user or job neither cascades into
audit rows nor is blocked by them; rows stay until retention purges them.

RLS: ``tenant_isolation`` only. ``audit_log:read`` is org-scoped, so a reader
inside a project still sees the whole org's log; the table is listed in
``PROJECT_POLICY_EXEMPT_TABLES`` in ``tests/backend/security/test_rls_coverage.py``.

Revision ID: ef7fe15a29ee
Revises: e48398256069
Create Date: 2026-10-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ef7fe15a29ee"
down_revision: Union[str, None] = "e48398256069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "audit_event"
_PURGE_SIGNATURE = "public.audit_event_purge(uuid, timestamptz, text, text, uuid)"

# UUIDv7: a v4 with its first 48 bits replaced by Unix milliseconds, and the
# version nibble turned from 4 into 7.
_UUID7 = """
CREATE OR REPLACE FUNCTION public.rhesis_uuid7() RETURNS uuid
LANGUAGE sql VOLATILE AS $$
    SELECT encode(
        set_bit(set_bit(
            overlay(
                uuid_send(gen_random_uuid())
                PLACING substring(
                    int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3
                )
                FROM 1 FOR 6
            ),
            52, 1), 53, 1),
        'hex')::uuid
$$
"""

_SET_RECORDED_AT = """
CREATE OR REPLACE FUNCTION public.set_recorded_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.recorded_at := clock_timestamp();
    RETURN NEW;
END;
$$
"""

# Shared by every append-only table. ``rhesis.purging`` names the one table a
# purge function is deleting from, for the rest of its transaction.
_REJECT_CHANGE = """
CREATE OR REPLACE FUNCTION public.reject_append_only_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('rhesis.purging', true) = TG_TABLE_NAME THEN
        RETURN NULL;
    END IF;
    RAISE EXCEPTION '% is append-only; % is not allowed', TG_TABLE_NAME, TG_OP;
END;
$$
"""

_PURGE = """
CREATE OR REPLACE FUNCTION public.audit_event_purge(
    p_organization_id uuid,
    p_before timestamptz,
    p_trace_id text,
    p_span_id text,
    p_job_id uuid DEFAULT NULL
) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_previous_org text := current_setting('app.current_organization', true);
    v_count bigint;
    v_oldest timestamptz;
BEGIN
    IF p_organization_id IS NULL OR p_before IS NULL THEN
        RAISE EXCEPTION 'audit_event_purge needs an organization and a cutoff';
    END IF;
    IF p_before > clock_timestamp() THEN
        RAISE EXCEPTION 'audit_event_purge cutoff % is in the future', p_before;
    END IF;

    -- FORCE ROW LEVEL SECURITY applies to the owner too, unless it bypasses RLS.
    PERFORM set_config('app.current_organization', p_organization_id::text, true);
    PERFORM set_config('rhesis.purging', 'audit_event', true);

    WITH gone AS (
        DELETE FROM public.audit_event
        WHERE organization_id = p_organization_id AND recorded_at < p_before
        RETURNING recorded_at
    )
    SELECT count(*), min(recorded_at) INTO v_count, v_oldest FROM gone;

    PERFORM set_config('rhesis.purging', '', true);

    INSERT INTO public.audit_event (
        organization_id, occurred_at, action, outcome, actor_type, channel,
        trace_id, span_id, job_id, changes
    ) VALUES (
        p_organization_id, clock_timestamp(), 'audit_log.purged', 'success', 'system', 'job',
        p_trace_id, p_span_id, p_job_id,
        jsonb_build_object('count', v_count, 'oldest', v_oldest, 'before', p_before)
    );

    PERFORM set_config('app.current_organization', coalesce(v_previous_org, ''), true);
    RETURN v_count;
END;
$$
"""

_TENANT_ISOLATION = f"""
CREATE POLICY tenant_isolation ON {_TABLE} AS PERMISSIVE FOR ALL TO public
USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization', true), '')::uuid))
"""

# Takes UPDATE, DELETE and TRUNCATE from every role the table's ACL lists, and
# gives the purge function to the roles that write (not to read-only roles).
_RESTRICT_GRANTS = f"""
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT pg_roles.rolname, bool_or(acl.privilege_type = 'INSERT') AS writes
        FROM pg_class c
        CROSS JOIN LATERAL aclexplode(c.relacl) acl
        JOIN pg_roles ON pg_roles.oid = acl.grantee
        WHERE c.oid = 'public.{_TABLE}'::regclass AND acl.grantee <> c.relowner
        GROUP BY pg_roles.rolname
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON public.{_TABLE} FROM %I', r.rolname);
        IF r.writes THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION {_PURGE_SIGNATURE} TO %I', r.rolname);
        END IF;
    END LOOP;
END;
$$
"""

# (index name, columns, postgresql_using, postgresql_ops)
_INDEXES = [
    # The list, newest first.
    (
        "ix_audit_event_org_occurred",
        ["organization_id", sa.text("occurred_at DESC"), "id"],
        None,
        None,
    ),
    # Action and resource-type filters; text_pattern_ops serves startswith(action, 'endpoint.').
    (
        "ix_audit_event_org_action",
        ["organization_id", "action", "occurred_at"],
        None,
        {"action": "text_pattern_ops"},
    ),
    # Retention and later sealing scan by insert time.
    ("ix_audit_event_recorded_at", ["recorded_at"], "brin", None),
]


def _columns() -> list:
    uuid = postgresql.UUID()
    ts = sa.TIMESTAMP(timezone=True)
    return [
        sa.Column("id", uuid, primary_key=True, server_default=sa.text("public.rhesis_uuid7()")),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=True),
        sa.Column("occurred_at", ts, nullable=False),
        sa.Column("recorded_at", ts, nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", uuid, nullable=True),
        sa.Column("actor_credential_id", sa.Text(), nullable=True),
        sa.Column("actor_credential_hint", sa.Text(), nullable=True),
        sa.Column("actor_label", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("resource_id", uuid, nullable=True),
        sa.Column("resource_label", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("span_id", sa.Text(), nullable=False),
        sa.Column("job_id", uuid, nullable=True),
        # A list of field changes; for audit_log.purged, an object {count, oldest, before}.
        sa.Column(
            "changes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Ciphertext (EncryptedString), only when the org opted in to content diffs.
        sa.Column("content_changes", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    op.execute(_UUID7)
    op.execute(_SET_RECORDED_AT)
    op.execute(_REJECT_CHANGE)

    op.create_table(_TABLE, *_columns())
    for name, columns, using, ops in _INDEXES:
        op.create_index(name, _TABLE, columns, postgresql_using=using, postgresql_ops=ops or {})

    op.execute(
        f"CREATE TRIGGER audit_event_recorded_at BEFORE INSERT ON {_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION public.set_recorded_at()"
    )
    op.execute(
        f"CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON {_TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.reject_append_only_change()"
    )

    op.execute(_TENANT_ISOLATION)
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")

    op.execute(_PURGE)
    op.execute(f"REVOKE ALL ON FUNCTION {_PURGE_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {_TABLE} FROM PUBLIC")
    op.execute(_RESTRICT_GRANTS)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_PURGE_SIGNATURE}")
    # DROP TABLE is not a DELETE or TRUNCATE, so the append-only trigger does not fire.
    op.drop_table(_TABLE)
    op.execute("DROP FUNCTION IF EXISTS public.reject_append_only_change()")
    op.execute("DROP FUNCTION IF EXISTS public.set_recorded_at()")
    op.execute("DROP FUNCTION IF EXISTS public.rhesis_uuid7()")
