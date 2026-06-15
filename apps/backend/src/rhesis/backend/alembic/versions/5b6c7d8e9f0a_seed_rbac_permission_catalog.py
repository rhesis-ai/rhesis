"""Seed RBAC permission catalog and built-in roles (SP7 data migration)

Populates the ``permission`` table with all 173 platform capabilities and is
the authoritative, self-healing seed for the five built-in roles
(Owner, Admin, Member, Viewer, None).

The catalog is the union of route-derived capabilities (resource×verb +
``@capability`` overrides) and capabilities declared on the ``Permission`` enum
but checked in handler/service code (e.g. ``member:manage``, ``role:manage``,
``recycle:view``) — see ``capabilities.enumerate_permission_enum``.

All inserts use ``ON CONFLICT DO NOTHING`` so the migration is idempotent and
safe to re-run.  Owner and Admin are *also* seeded by the preceding org-member
backfill migration (371c3c3cd787, which must create them so its backfill JOIN
resolves); the overlap is harmless.  Seeding all five here means a database that
somehow lost a built-in role recovers on the next ``upgrade`` rather than
depending on the old startup sync (now removed).

No ``role_permission`` rows are inserted for built-in roles — the EE
``PermissionAuthorizationProvider`` computes their permission sets from code
via ``permissions_for_built_in_role()``, so they never need stored mappings.

Custom roles continue to use ``role_permission`` rows (written via the API).

Developer rule
--------------
When you add or remove a capability (new router, new ``@capability()``
override, changed HTTP method), add a follow-up migration that inserts /
retires the affected ``permission`` row.  The drift guard test
``tests/backend/security/test_capability_catalog.py`` will catch any gap
in CI.

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5b6c7d8e9f0a"
down_revision: Union[str, None] = "4a5b6c7d8e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Capability catalog — generated from get_all_capabilities() (route-derived ∪
# Permission enum).  Columns: (name, display_name, resource_type, action, scope)
# Update this list whenever a capability is added/removed (write a migration).
# ---------------------------------------------------------------------------
_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("api_clients:manage", "Manage api clients", "api_clients", "manage", "organization"),
    ("architect:create", "Create architect", "architect", "create", "project"),
    ("architect:delete", "Delete architect", "architect", "delete", "project"),
    ("architect:read", "Read architect", "architect", "read", "project"),
    ("architect:update", "Update architect", "architect", "update", "project"),
    ("behavior:create", "Create behavior", "behavior", "create", "project"),
    ("behavior:delete", "Delete behavior", "behavior", "delete", "project"),
    ("behavior:read", "Read behavior", "behavior", "read", "project"),
    ("behavior:update", "Update behavior", "behavior", "update", "project"),
    ("category:create", "Create category", "category", "create", "project"),
    ("category:delete", "Delete category", "category", "delete", "project"),
    ("category:read", "Read category", "category", "read", "project"),
    ("category:update", "Update category", "category", "update", "project"),
    ("comment:create", "Create comments", "comment", "create", "project"),
    ("comment:delete", "Delete comments", "comment", "delete", "project"),
    ("comment:react", "React comments", "comment", "react", "project"),
    ("comment:read", "Read comments", "comment", "read", "project"),
    ("comment:update", "Update comments", "comment", "update", "project"),
    ("connector:create", "Create connector", "connector", "create", "project"),
    ("connector:read", "Read connector", "connector", "read", "project"),
    ("demographic:create", "Create demographic", "demographic", "create", "project"),
    ("demographic:delete", "Delete demographic", "demographic", "delete", "project"),
    ("demographic:read", "Read demographic", "demographic", "read", "project"),
    ("demographic:update", "Update demographic", "demographic", "update", "project"),
    ("dimension:create", "Create dimension", "dimension", "create", "project"),
    ("dimension:delete", "Delete dimension", "dimension", "delete", "project"),
    ("dimension:read", "Read dimension", "dimension", "read", "project"),
    ("dimension:update", "Update dimension", "dimension", "update", "project"),
    ("endpoint:create", "Create endpoints", "endpoint", "create", "project"),
    ("endpoint:delete", "Delete endpoints", "endpoint", "delete", "project"),
    ("endpoint:read", "Read endpoints", "endpoint", "read", "project"),
    ("endpoint:update", "Update endpoints", "endpoint", "update", "project"),
    ("experiment:create", "Create experiments", "experiment", "create", "project"),
    ("experiment:delete", "Delete experiments", "experiment", "delete", "project"),
    ("experiment:read", "Read experiments", "experiment", "read", "project"),
    ("experiment:update", "Update experiments", "experiment", "update", "project"),
    ("explorer:create", "Create explorer", "explorer", "create", "project"),
    ("explorer:delete", "Delete explorer", "explorer", "delete", "project"),
    ("explorer:read", "Read explorer", "explorer", "read", "project"),
    ("explorer:update", "Update explorer", "explorer", "update", "project"),
    ("feedback:create", "Create feedback", "feedback", "create", "project"),
    ("file:create", "Create files", "file", "create", "project"),
    ("file:delete", "Delete files", "file", "delete", "project"),
    ("file:import", "Import files", "file", "import", "project"),
    ("file:read", "Read files", "file", "read", "project"),
    ("file:update", "Update files", "file", "update", "project"),
    ("file_import:create", "Create file import", "file_import", "create", "project"),
    ("file_import:delete", "Delete file import", "file_import", "delete", "project"),
    ("file_import:read", "Read file import", "file_import", "read", "project"),
    ("garak:create", "Create garak", "garak", "create", "project"),
    ("garak:read", "Read garak", "garak", "read", "project"),
    ("job:read", "Read job", "job", "read", "project"),
    ("member:create", "Create member", "member", "create", "organization"),
    ("member:delete", "Delete member", "member", "delete", "organization"),
    ("member:manage", "Manage member", "member", "manage", "organization"),
    ("member:read", "Read member", "member", "read", "organization"),
    ("member:update", "Update member", "member", "update", "organization"),
    ("metric:create", "Create metrics", "metric", "create", "project"),
    ("metric:delete", "Delete metrics", "metric", "delete", "project"),
    ("metric:read", "Read metrics", "metric", "read", "project"),
    ("metric:update", "Update metrics", "metric", "update", "project"),
    ("model:create", "Create models", "model", "create", "project"),
    ("model:delete", "Delete models", "model", "delete", "project"),
    ("model:read", "Read models", "model", "read", "project"),
    ("model:update", "Update models", "model", "update", "project"),
    ("organization:create", "Create organization", "organization", "create", "organization"),
    ("organization:read", "Read organization", "organization", "read", "organization"),
    ("organization:update", "Update organization", "organization", "update", "organization"),
    ("parameter:create", "Create parameter", "parameter", "create", "project"),
    ("parameter:delete", "Delete parameter", "parameter", "delete", "project"),
    ("parameter:read", "Read parameter", "parameter", "read", "project"),
    ("parameter:update", "Update parameter", "parameter", "update", "project"),
    ("preflight:create", "Create preflight", "preflight", "create", "project"),
    ("project:create", "Create project", "project", "create", "organization"),
    ("project:delete", "Delete project", "project", "delete", "project"),
    ("project:read", "Read project", "project", "read", "project"),
    ("project:update", "Update project", "project", "update", "project"),
    ("project_member:manage", "Manage project member", "project_member", "manage", "project"),
    ("prompt:create", "Create prompt", "prompt", "create", "project"),
    ("prompt:delete", "Delete prompt", "prompt", "delete", "project"),
    ("prompt:read", "Read prompt", "prompt", "read", "project"),
    ("prompt:update", "Update prompt", "prompt", "update", "project"),
    ("prompt_template:create", "Create prompt template", "prompt_template", "create", "project"),
    ("prompt_template:delete", "Delete prompt template", "prompt_template", "delete", "project"),
    ("prompt_template:read", "Read prompt template", "prompt_template", "read", "project"),
    ("prompt_template:update", "Update prompt template", "prompt_template", "update", "project"),
    ("recycle:delete", "Delete recycle", "recycle", "delete", "organization"),
    ("recycle:purge", "Purge recycle", "recycle", "purge", "organization"),
    ("recycle:read", "Read recycle", "recycle", "read", "organization"),
    ("recycle:restore", "Restore recycle", "recycle", "restore", "organization"),
    ("recycle:view", "View recycle", "recycle", "view", "organization"),
    ("response_pattern:create", "Create response pattern", "response_pattern", "create", "project"),
    ("response_pattern:delete", "Delete response pattern", "response_pattern", "delete", "project"),
    ("response_pattern:read", "Read response pattern", "response_pattern", "read", "project"),
    ("response_pattern:update", "Update response pattern", "response_pattern", "update", "project"),
    ("risk:create", "Create risk", "risk", "create", "project"),
    ("risk:delete", "Delete risk", "risk", "delete", "project"),
    ("risk:read", "Read risk", "risk", "read", "project"),
    ("risk:update", "Update risk", "risk", "update", "project"),
    ("role:manage", "Manage role", "role", "manage", "organization"),
    ("role:read", "Read role", "role", "read", "organization"),
    ("service:create", "Create service", "service", "create", "project"),
    ("service:read", "Read service", "service", "read", "project"),
    ("source:create", "Create source", "source", "create", "project"),
    ("source:delete", "Delete source", "source", "delete", "project"),
    ("source:read", "Read source", "source", "read", "project"),
    ("source:update", "Update source", "source", "update", "project"),
    ("sso:manage", "Manage sso", "sso", "manage", "organization"),
    ("status:create", "Create status", "status", "create", "project"),
    ("status:delete", "Delete status", "status", "delete", "project"),
    ("status:read", "Read status", "status", "read", "project"),
    ("status:update", "Update status", "status", "update", "project"),
    ("tag:create", "Create tag", "tag", "create", "project"),
    ("tag:delete", "Delete tag", "tag", "delete", "project"),
    ("tag:read", "Read tag", "tag", "read", "project"),
    ("tag:update", "Update tag", "tag", "update", "project"),
    ("task:create", "Create tasks", "task", "create", "project"),
    ("task:delete", "Delete tasks", "task", "delete", "project"),
    ("task:read", "Read tasks", "task", "read", "project"),
    ("task:update", "Update tasks", "task", "update", "project"),
    ("telemetry:create", "Create telemetry", "telemetry", "create", "project"),
    ("telemetry:delete", "Delete telemetry", "telemetry", "delete", "project"),
    ("telemetry:read", "Read telemetry", "telemetry", "read", "project"),
    ("telemetry:update", "Update telemetry", "telemetry", "update", "project"),
    ("test:create", "Create tests", "test", "create", "project"),
    ("test:delete", "Delete tests", "test", "delete", "project"),
    ("test:read", "Read tests", "test", "read", "project"),
    ("test:update", "Update tests", "test", "update", "project"),
    (
        "test_configuration:create",
        "Create test configurations",
        "test_configuration",
        "create",
        "project",
    ),
    (
        "test_configuration:delete",
        "Delete test configurations",
        "test_configuration",
        "delete",
        "project",
    ),
    (
        "test_configuration:read",
        "Read test configurations",
        "test_configuration",
        "read",
        "project",
    ),
    (
        "test_configuration:update",
        "Update test configurations",
        "test_configuration",
        "update",
        "project",
    ),
    ("test_context:create", "Create test context", "test_context", "create", "project"),
    ("test_context:delete", "Delete test context", "test_context", "delete", "project"),
    ("test_context:read", "Read test context", "test_context", "read", "project"),
    ("test_context:update", "Update test context", "test_context", "update", "project"),
    ("test_result:create", "Create test results", "test_result", "create", "project"),
    ("test_result:delete", "Delete test results", "test_result", "delete", "project"),
    ("test_result:read", "Read test results", "test_result", "read", "project"),
    ("test_result:update", "Update test results", "test_result", "update", "project"),
    ("test_run:create", "Create test runs", "test_run", "create", "project"),
    ("test_run:delete", "Delete test runs", "test_run", "delete", "project"),
    ("test_run:execute", "Execute test runs", "test_run", "execute", "project"),
    ("test_run:read", "Read test runs", "test_run", "read", "project"),
    ("test_run:update", "Update test runs", "test_run", "update", "project"),
    ("test_set:create", "Create test sets", "test_set", "create", "project"),
    ("test_set:delete", "Delete test sets", "test_set", "delete", "project"),
    ("test_set:execute", "Execute test sets", "test_set", "execute", "project"),
    ("test_set:generate", "Generate test sets", "test_set", "generate", "project"),
    ("test_set:read", "Read test sets", "test_set", "read", "project"),
    ("test_set:update", "Update test sets", "test_set", "update", "project"),
    ("token:create", "Create token", "token", "create", "organization"),
    ("token:delete", "Delete token", "token", "delete", "organization"),
    ("token:manage", "Manage token", "token", "manage", "organization"),
    ("token:read", "Read token", "token", "read", "organization"),
    ("token:update", "Update token", "token", "update", "organization"),
    ("tool:create", "Create tool", "tool", "create", "project"),
    ("tool:delete", "Delete tool", "tool", "delete", "project"),
    ("tool:read", "Read tool", "tool", "read", "project"),
    ("tool:update", "Update tool", "tool", "update", "project"),
    ("topic:create", "Create topic", "topic", "create", "project"),
    ("topic:delete", "Delete topic", "topic", "delete", "project"),
    ("topic:read", "Read topic", "topic", "read", "project"),
    ("topic:update", "Update topic", "topic", "update", "project"),
    ("type_lookup:create", "Create type lookup", "type_lookup", "create", "project"),
    ("type_lookup:delete", "Delete type lookup", "type_lookup", "delete", "project"),
    ("type_lookup:read", "Read type lookup", "type_lookup", "read", "project"),
    ("type_lookup:update", "Update type lookup", "type_lookup", "update", "project"),
    ("use_case:create", "Create use case", "use_case", "create", "project"),
    ("use_case:delete", "Delete use case", "use_case", "delete", "project"),
    ("use_case:read", "Read use case", "use_case", "read", "project"),
    ("use_case:update", "Update use case", "use_case", "update", "project"),
    ("websocket:create", "Create websocket", "websocket", "create", "project"),
]

# All five built-in roles, seeded idempotently. Owner/Admin overlap with
# 371c3c3cd787 (harmless via ON CONFLICT). Levels must match
# BUILT_IN_ROLE_LEVELS in ee/rbac/models.py. No role_permission rows:
# built-in permissions are computed from code.
_BUILT_IN_ROLES: list[tuple[str, int]] = [
    ("Owner", 100),
    ("Admin", 80),
    ("Member", 60),
    ("Viewer", 40),
    ("None", 0),
]


def upgrade() -> None:
    # op.execute() does not support bound parameters; use the bind connection,
    # which accepts a list of param dicts (executemany) for the seed rows.
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO permission (
                id, name, display_name, resource_type, action, scope,
                is_retired, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), :name, :display_name, :resource_type,
                :action, :scope, false, now(), now()
            )
            ON CONFLICT (name) DO NOTHING
            """
        ),
        [
            {
                "name": name,
                "display_name": display_name,
                "resource_type": resource_type,
                "action": action,
                "scope": scope,
            }
            for name, display_name, resource_type, action, scope in _PERMISSIONS
        ],
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO role (
                id, name, display_name, scope, level,
                is_built_in, organization_id, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), :name, :name, 'organization',
                :level, true, NULL, now(), now()
            )
            ON CONFLICT DO NOTHING
            """
        ),
        [{"name": name, "level": level} for name, level in _BUILT_IN_ROLES],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM permission WHERE name = ANY(:names)"),
        {"names": [name for name, *_ in _PERMISSIONS]},
    )
    # Only remove the roles this migration introduced. Owner/Admin are owned by
    # 371c3c3cd787 (its backfill depends on them) and are left in place.
    conn.execute(
        sa.text("DELETE FROM role WHERE name = ANY(:names) AND is_built_in = true"),
        {"names": ["Member", "Viewer", "None"]},
    )
