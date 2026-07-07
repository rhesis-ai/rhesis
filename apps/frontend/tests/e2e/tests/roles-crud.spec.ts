import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { RbacMockHelper } from '../helpers/RbacMockHelper';
import { OrgSettingsPage } from '../pages/OrgSettingsPage';
import {
  openDrawer,
  waitForDrawerClosed,
  confirmDeleteDialog,
} from '../helpers/CrudHelper';

/**
 * RBAC Roles tab — create/edit/delete a custom role.
 *
 * Runs with the RBAC feature flag forced on (RbacMockHelper.mockFeaturesEnabled)
 * — the default mock-backend response is community/off, matching production
 * where RBAC ships dark until licensed. See roles-unlicensed.spec.ts for the
 * default (RBAC-off) fallback behavior.
 */
test.describe('RBAC Roles — CRUD @mocked', () => {
  test.beforeEach(async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockLayoutPrerequisites();

    const rbac = new RbacMockHelper(page);
    await rbac.mockFeaturesEnabled();
    // Owner-equivalent ambient permission set: enabling RBAC activates
    // scope-level gating for every page (not just the Roles tab), so the
    // surrounding Organization Settings page needs organization:read too.
    await rbac.mockPermissions([
      'organization:read',
      'organization:update',
      'member:read',
      'member:manage',
      'role:read',
      'role:manage',
      'token:manage',
    ]);
    await rbac.mockOrganizationMembersCrud();
    await rbac.mockRolesCrud();
  });

  test('lists built-in and custom roles', async ({ page }) => {
    const orgSettings = new OrgSettingsPage(page);
    await orgSettings.goto();
    await orgSettings.openRolesTab();

    await expect(
      page.getByRole('heading', { name: 'Built-in Roles' })
    ).toBeVisible();
    await expect(page.getByText('Owner')).toBeVisible();
    await expect(page.getByText('Auditor')).toBeVisible();
  });

  test('creates a custom role with just a name', async ({ page }) => {
    const UNIQUE_NAME = `E2E Role ${Date.now()}`;
    const orgSettings = new OrgSettingsPage(page);
    await orgSettings.goto();
    await orgSettings.openRolesTab();

    await page.getByRole('button', { name: /new role/i }).click();
    const drawer = openDrawer(page);
    await drawer.getByLabel(/role name/i).fill(UNIQUE_NAME);
    await drawer.getByRole('button', { name: /create role/i }).click();
    await waitForDrawerClosed(page);

    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 10_000 });
  });

  test("edits a custom role's display name", async ({ page }) => {
    const orgSettings = new OrgSettingsPage(page);
    await orgSettings.goto();
    await orgSettings.openRolesTab();

    await page
      .locator('tr', { hasText: 'Auditor' })
      .getByRole('button', { name: /^edit$/i })
      .click();

    const drawer = openDrawer(page);
    await drawer.getByLabel(/role name/i).fill('Compliance Auditor');
    await drawer.getByRole('button', { name: /save changes/i }).click();
    await waitForDrawerClosed(page);

    await expect(page.getByText('Compliance Auditor')).toBeVisible({
      timeout: 10_000,
    });
  });

  test('deletes a custom role', async ({ page }) => {
    const orgSettings = new OrgSettingsPage(page);
    await orgSettings.goto();
    await orgSettings.openRolesTab();

    await page
      .locator('tr', { hasText: 'Auditor' })
      .getByRole('button', { name: /^edit$/i })
      .click();

    const drawer = openDrawer(page);
    await drawer.getByRole('button', { name: /delete role/i }).click();
    await confirmDeleteDialog(page);
    await waitForDrawerClosed(page);

    await expect(page.getByText('Auditor')).not.toBeVisible({
      timeout: 10_000,
    });
  });
});
