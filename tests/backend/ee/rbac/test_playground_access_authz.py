"""Playground access authorization.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_playground_access_authz.py -v
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.auth.capabilities import Permission, get_all_capabilities
from rhesis.backend.ee.rbac.models import permissions_for_built_in_role


@pytest.mark.ee
class TestPlaygroundBuiltInRolePermissions:
    def test_viewer_cannot_use_playground(self):
        perms = permissions_for_built_in_role("Viewer", get_all_capabilities())
        assert Permission.Playground.USE not in perms

    def test_member_can_use_playground(self):
        perms = permissions_for_built_in_role("Member", get_all_capabilities())
        assert Permission.Playground.USE in perms

    def test_owner_can_use_playground(self):
        perms = permissions_for_built_in_role("Owner", get_all_capabilities())
        assert Permission.Playground.USE in perms
