import { type Page, expect } from '@playwright/test';

/**
 * Shared helpers for CRUD-style E2E tests.
 *
 * Provides lightweight utilities to reduce setup/teardown boilerplate and
 * keep individual spec files focused on the behaviour under test.
 */

/**
 * Select a data-grid row that contains the given text by clicking its checkbox.
 * Works for any MUI DataGrid rendered with role="row" and role="grid".
 */
export async function selectGridRowByText(page: Page, text: string) {
  const row = page.locator('[role="row"]', { hasText: text });
  await row.locator('input[type="checkbox"]').click();
}

/**
 * Delete a grid row via the hover-revealed row-actions delete icon.
 * Grids use createRowActionsColumn — delete is the trailing icon button.
 */
export async function deleteGridRowByText(page: Page, text: string) {
  const row = page
    .locator('.MuiDataGrid-row')
    .filter({ hasText: text })
    .first();
  await row.scrollIntoViewIfNeeded();
  await row.hover();
  // Row-actions stay visibility:hidden until row:hover — force-click delete icon.
  const deleteBtn = row.locator('.row-actions button').last();
  await deleteBtn.click({ force: true });
}

/** Wait until a data grid row containing the given text is visible. */
export async function expectGridRowVisible(page: Page, text: string) {
  const row = page
    .locator('.MuiDataGrid-row')
    .filter({ hasText: text })
    .first();
  await expect(row).toBeVisible({ timeout: 15_000 });
}

/**
 * Locator for an open MUI drawer (BaseDrawer titles are plain Typography).
 * Pass `title` to scope to one specific drawer — required whenever more
 * than one drawer can be mounted on the page (even closed), since a
 * just-closed drawer's `aria-hidden` attribute can lag its mount by a
 * frame, which otherwise trips Playwright's strict-mode "resolved to N
 * elements" check against the unscoped locator.
 */
export function openDrawer(page: Page, title?: string | RegExp) {
  const drawers = page.locator('.MuiDrawer-root:not([aria-hidden="true"])');
  if (title === undefined) return drawers;
  // BaseDrawer title is Typography — avoid matching the footer save button.
  return drawers.filter({ has: page.getByRole('paragraph', { name: title }) });
}

/** Wait until the open drawer shows the expected title text. */
export async function expectOpenDrawerTitle(
  page: Page,
  title: string | RegExp,
  timeout = 10_000
) {
  const drawer = openDrawer(page);
  await drawer.waitFor({ state: 'visible', timeout });
  // BaseDrawer title is Typography — avoid matching the footer save button.
  await expect(
    drawer.getByRole('paragraph').filter({ hasText: title }).first()
  ).toBeVisible({ timeout });
}

/**
 * Wait until no drawer is open. Pass `title` to scope to one specific
 * drawer when other drawers may be mounted-but-closed on the page.
 */
export async function waitForDrawerClosed(
  page: Page,
  opts: { title?: string | RegExp; timeout?: number } = {}
) {
  const { title, timeout = 15_000 } = opts;
  await openDrawer(page, title).waitFor({ state: 'hidden', timeout });
}

/** Wait until a drawer heading is no longer visible (BaseDrawer uses role=presentation). */
export async function waitForDrawerHeadingHidden(
  page: Page,
  title: string | RegExp,
  timeout = 15_000
) {
  await waitForDrawerClosed(page, { title, timeout });
}

/** UUID that is valid but unlikely to exist in Quick Start seed data. */
export const NON_EXISTENT_UUID = '00000000-0000-0000-0000-000000000099';

/**
 * Confirm a MUI deletion dialog by clicking the primary destructive button.
 * Waits for the dialog to close after confirmation.
 */
export async function confirmDeleteDialog(page: Page) {
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /delete/i }).click();
  await dialog.waitFor({ state: 'hidden', timeout: 15_000 });
}

/**
 * Cancel a MUI deletion dialog by clicking the Cancel button.
 */
export async function cancelDeleteDialog(page: Page) {
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /cancel/i }).click();
  await dialog.waitFor({ state: 'hidden', timeout: 10_000 });
}

/**
 * Wait for a MUI Drawer (role="presentation") to become visible after opening.
 */
export async function waitForDrawer(page: Page, timeout = 10_000) {
  await page.getByRole('presentation').waitFor({ state: 'visible', timeout });
}

/**
 * Close the currently open MUI Drawer by pressing Escape.
 */
export async function closeDrawerByEscape(page: Page) {
  await page.keyboard.press('Escape');
}

/**
 * Fill a MUI Select (role="button" with aria-haspopup="listbox") and pick an option.
 * Scoped to the drawer presentation element to avoid accidentally matching page-level selects.
 *
 * Returns false if the option could not be found (caller should skip).
 */
export async function selectDrawerOption(
  page: Page,
  optionPattern: string | RegExp,
  selectIndex = 0
): Promise<boolean> {
  const selectBtn = page
    .locator('[role="presentation"] [aria-haspopup="listbox"]')
    .nth(selectIndex);

  const visible = await selectBtn
    .isVisible({ timeout: 5_000 })
    .catch(() => false);
  if (!visible) return false;

  await selectBtn.click();

  const option = page.getByRole('option', { name: optionPattern });
  const found = await option.isVisible({ timeout: 8_000 }).catch(() => false);
  if (!found) {
    await page.keyboard.press('Escape');
    return false;
  }

  await option.click();
  return true;
}
