"""EE RBAC catalog — roles, permissions, and organization membership.

SP7 deliverables:
- ORM models: ``Role``, ``Permission``, ``RolePermission``, ``OrganizationMember``
- Catalog seeded via Alembic data migrations (not a runtime sync)
- Built-in roles (Owner/Admin/Member/Viewer/None) compute permissions from code
  via ``permissions_for_built_in_role``; no ``role_permission`` rows needed

SP8 deliverables:
- ``PermissionAuthorizationProvider`` — EE PDP that resolves roles and checks
  permissions; built-ins evaluated from code, custom roles from ``role_permission``
- Pydantic schemas for the role and assignment APIs
- Role CRUD + org/project assignment router (``/rbac/...``)
- Backfill migration: ``organization_member`` seeded from existing org data
- ``is_superuser`` column dropped from ``user``
"""
