"""EE RBAC catalog — roles, permissions, and organization membership.

SP7 deliverables:
- ORM models: ``Role``, ``Permission``, ``RolePermission``, ``OrganizationMember``
- Idempotent startup sync: ``sync_rbac_catalog(db)``
- Built-in role seeding (Owner/Admin/Member/Viewer/None) from the capability registry
"""
