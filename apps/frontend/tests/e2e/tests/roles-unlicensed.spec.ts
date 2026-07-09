import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { OrgTeamPage } from '../pages/OrgTeamPage';

const OTHER_MEMBER = {
  id: 'd0000000-0000-0000-0000-000000000099',
  email: 'other-member@local.dev',
  name: 'Other Member',
  organization_id: 'e2e00000-0000-0000-0000-000000000002',
  is_active: true,
};

/**
 * Regression test for the pre-fix OrgRoleChip bug: with RBAC unlicensed
 * (mock-backend's default `GET /features` response is community/off, left
 * unmocked here) a 404 from `GET /rbac/organization-members` used to leave
 * the chip stuck in its loading skeleton forever. OrgRoleChip.tsx:73-79 now
 * catches the failure and falls through to the assignable Select instead.
 *
 * Does not force RBAC on (contrast with roles-crud.spec.ts) — this exercises
 * exactly the default, unlicensed state real orgs start in.
 */
test.describe('RBAC Roles — unlicensed fallback @mocked', () => {
  test('org role chip exits its loading skeleton on a 404 from /rbac/organization-members', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockLayoutPrerequisites();
    await mock.mockList('/users', [OTHER_MEMBER]);
    await mock.mockError('/rbac/organization-members', 404);

    const orgTeam = new OrgTeamPage(page);
    await orgTeam.goto();
    await orgTeam.expectLoaded();

    const roleCell = orgTeam.roleCellForRow(OTHER_MEMBER.email);
    await expect(roleCell).toBeVisible({ timeout: 15_000 });
    await expect(roleCell.locator('.MuiSkeleton-root')).toHaveCount(0, {
      timeout: 15_000,
    });
  });
});
