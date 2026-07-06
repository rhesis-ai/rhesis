import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { RbacMockHelper } from '../helpers/RbacMockHelper';
import { OrgTeamPage } from '../pages/OrgTeamPage';

const TARGET_MEMBER = {
  id: 'd0000000-0000-0000-0000-000000000042',
  email: 'target-member@local.dev',
  name: 'Target Member',
  organization_id: 'e2e00000-0000-0000-0000-000000000002',
  is_active: true,
};

// Owner (session user) + TARGET_MEMBER starting as Viewer.
const ORG_MEMBERS = [
  {
    id: 'c0000000-0000-0000-0000-000000000001',
    organization_id: 'e2e00000-0000-0000-0000-000000000002',
    user_id: 'e2e00000-0000-0000-0000-000000000001',
    role_id: 'a0000000-0000-0000-0000-000000000001',
  },
  {
    id: 'c0000000-0000-0000-0000-000000000002',
    organization_id: 'e2e00000-0000-0000-0000-000000000002',
    user_id: TARGET_MEMBER.id,
    role_id: 'a0000000-0000-0000-0000-000000000004',
    role: {
      id: 'a0000000-0000-0000-0000-000000000004',
      name: 'viewer',
      display_name: 'Viewer',
      description: 'Read-only access.',
      scope: 'organization',
      level: 40,
      is_built_in: true,
      organization_id: null,
      permissions: [],
      member_count: 1,
    },
  },
];

/**
 * Org role assignment via the chip on the Team page (OrgTeamPage's
 * `orgRole` grid column, rendered by OrgRoleChip). Complements
 * roles-crud.spec.ts (which covers the Roles tab itself) with the other
 * half of the RBAC authoring UI: assigning a role to a member.
 */
test.describe('RBAC Team — org role assignment @mocked', () => {
  test.beforeEach(async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockLayoutPrerequisites();
    await mock.mockList('/users', [TARGET_MEMBER]);

    const rbac = new RbacMockHelper(page);
    await rbac.mockFeaturesEnabled();
    await rbac.mockPermissions([
      'organization:read',
      'member:read',
      'member:manage',
      'role:read',
    ]);
    await rbac.mockOrganizationMembersCrud(ORG_MEMBERS);
    await rbac.mockRolesCrud();
  });

  test('assigns a new org role to a member via the chip', async ({
    page,
  }) => {
    const orgTeam = new OrgTeamPage(page);
    await orgTeam.goto();
    await orgTeam.expectLoaded();

    const roleCell = orgTeam.roleCellForRow(TARGET_MEMBER.email);
    await expect(roleCell.getByText('Viewer')).toBeVisible({
      timeout: 15_000,
    });

    await roleCell.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Admin' }).click();

    await expect(roleCell.getByText('Admin')).toBeVisible({ timeout: 10_000 });
  });
});
