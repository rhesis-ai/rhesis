import { test, expect } from '@playwright/test';
import { OrgSettingsPage } from '../pages/OrgSettingsPage';
import { OrgTeamPage } from '../pages/OrgTeamPage';

test.describe('Organization Settings @sanity', () => {
  test('org settings page loads without error', async ({ page }) => {
    const settings = new OrgSettingsPage(page);
    await settings.goto();
    await settings.expectLoaded();
  });

  test('org settings page shows overview heading', async ({ page }) => {
    const settings = new OrgSettingsPage(page);
    await settings.goto();
    await settings.expectLoaded();
    await settings.expectHeadingVisible();
  });

  test('org settings page renders form fields', async ({ page }) => {
    const settings = new OrgSettingsPage(page);
    await settings.goto();
    await settings.expectContentVisible();
  });

  test('org settings page has a valid page title', async ({ page }) => {
    await page.goto('/organizations/settings');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});

test.describe('Organization Team @sanity', () => {
  test('org team page loads without error', async ({ page }) => {
    const team = new OrgTeamPage(page);
    await team.goto();
    await team.expectLoaded();
  });

  test('org team page renders invite form', async ({ page }) => {
    const team = new OrgTeamPage(page);
    await team.goto();
    await team.expectInviteFormVisible();
  });

  test('org team page shows members area', async ({ page }) => {
    const team = new OrgTeamPage(page);
    await team.goto();
    await team.expectMembersAreaVisible();
  });

  test('org team page has a valid page title', async ({ page }) => {
    await page.goto('/organizations/team');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
