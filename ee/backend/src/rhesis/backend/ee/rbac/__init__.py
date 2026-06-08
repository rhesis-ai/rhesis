"""EE RBAC catalog — roles, permissions, and organization membership.

SP7 deliverables:
- ORM models: ``Role``, ``Permission``, ``RolePermission``, ``OrganizationMember``
- Idempotent startup sync: ``sync_rbac_catalog(db)``
- Built-in role seeding (Owner/Admin/Member/Viewer/None) from the capability registry

SP8 deliverables:
- ``PermissionAuthorizationProvider`` — EE PDP that resolves roles and checks
  the permission table; installed at EE bootstrap via ``set_authorization_provider``
- Pydantic schemas for the role and assignment APIs
- Role CRUD + org/project assignment router (``/rbac/...``)
- Backfill migration: ``organization_member`` seeded from existing org data
- ``is_superuser`` column dropped from ``user``
"""
