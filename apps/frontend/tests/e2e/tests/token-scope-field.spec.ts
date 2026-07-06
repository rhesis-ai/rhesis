import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { RbacMockHelper } from '../helpers/RbacMockHelper';
import { TokensPage } from '../pages/TokensPage';
import {
  expectOpenDrawerTitle,
  openDrawer,
  selectDrawerOption,
} from '../helpers/CrudHelper';

/**
 * TokenScopeField (EE) — restricting a new API token to a role's permission
 * set. Renders inside CreateTokenDrawer regardless of the RBAC feature flag
 * (it only needs `GET /rbac/roles` to return an assignable role), but this
 * test forces RBAC on for realism — the real backend's `/rbac/*` router is
 * itself gated by `require_feature`, so roles would never be reachable while
 * unlicensed.
 */
test.describe('API Tokens — scoped token creation @mocked', () => {
  test.beforeEach(async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockLayoutPrerequisites();

    const rbac = new RbacMockHelper(page);
    await rbac.mockFeaturesEnabled();
    await rbac.mockPermissions(['token:manage']);
    await rbac.mockRolesCrud();
  });

  test('scopes a new token to a role and sends its permissions', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-scoped-token-${Date.now()}`;
    const captured: { body?: { name?: string; scopes?: string[] } } = {};

    // Anchored to the /api/v1 prefix (not MockApiHelper's optional-prefix
    // convention) — a bare `/tokens` pattern also matches the frontend's own
    // `/tokens` page navigation, which would hijack the page load itself.
    await page.route(/\/api\/v1\/tokens(\?|$)/, async route => {
      const method = route.request().method();
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: { 'x-total-count': '0' },
          body: JSON.stringify([]),
        });
      }
      if (method !== 'POST') return route.fallback();
      const body = route.request().postDataJSON() as {
        name?: string;
        scopes?: string[];
      };
      captured.body = body;
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'e2e-fake-token-value',
          token_obfuscated: 'e2e-****-value',
          token_type: 'bearer',
          expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
          name: body.name,
          scopes: body.scopes,
        }),
      });
    });

    const tokensPage = new TokensPage(page);
    await tokensPage.goto();
    await tokensPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tokensPage.openCreateTokenModal();
    const drawer = openDrawer(page);
    await drawer.getByRole('textbox', { name: /token name/i }).fill(UNIQUE_NAME);

    await expect(tokensPage.scopeField).toBeVisible({ timeout: 10_000 });
    await drawer.getByRole('radio', { name: /restricted/i }).click();
    const found = await selectDrawerOption(page, 'Auditor', 1);
    expect(found, 'Role template select did not offer an "Auditor" option').toBe(
      true
    );

    // Auditor holds the full View-level read set for the test-resources area
    // — the permission-summary chip proves the scope-preview UI derived the
    // area level correctly from that set, not just that a role was picked.
    await expect(page.getByText('Permission summary')).toBeVisible();
    await expect(page.getByText(/Test Resources: View/i)).toBeVisible();

    await drawer.getByRole('button', { name: /^create$/i }).click();
    await expectOpenDrawerTitle(page, /your new api token/i, 15_000);

    expect(captured.body?.name).toBe(UNIQUE_NAME);
    expect(captured.body?.scopes).toEqual(
      expect.arrayContaining(['test_set:read', 'test:read', 'task:read'])
    );
  });
});
