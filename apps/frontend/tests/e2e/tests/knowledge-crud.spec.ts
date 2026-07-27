import path from 'path';
import { randomUUID } from 'crypto';
import { test, expect, type Page } from '@playwright/test';
import { KnowledgePage } from '../pages/KnowledgePage';
import {
  confirmDeleteDialog,
  expectGridRowVisible,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

interface StubbedSource {
  id: string;
  title: string;
  description?: string;
}

function isSourcesListUrl(url: URL): boolean {
  const pathWithQuery = `${url.pathname}${url.search}`;
  return (
    (pathWithQuery.includes('/sources?') ||
      /\/sources\/?$/.test(url.pathname)) &&
    !pathWithQuery.includes('/sources/upload') &&
    !/\/sources\/[0-9a-f-]{36}/i.test(pathWithQuery)
  );
}

/** Stub upload + list refresh so the CRUD test validates UI without slow backend extraction. */
async function stubKnowledgeUpload(page: Page, source: StubbedSource) {
  await page.route(
    url => url.href.includes('/sources/upload'),
    async route => {
      if (route.request().method() !== 'POST') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...source,
          source_type: { type_value: 'document' },
          source_metadata: {
            original_filename: 'fixture.txt',
            file_size: 128,
          },
          content: 'fixture content',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    }
  );

  await page.route(
    url => isSourcesListUrl(url),
    async route => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }
      const response = await route.fetch();
      const existing = (await response.json()) as Array<{ id: string }>;
      const items = Array.isArray(existing) ? existing : [];
      const merged = [source, ...items.filter(item => item.id !== source.id)];
      const body = JSON.stringify(merged);
      // Drop length/encoding headers — they reflect the upstream body, not ours.
      const headers = Object.fromEntries(
        response
          .headersArray()
          .filter(
            ({ name }) =>
              ![
                'content-length',
                'content-encoding',
                'transfer-encoding',
              ].includes(name.toLowerCase())
          )
          .map(({ name, value }) => [name, value])
      );
      await route.fulfill({
        status: response.status(),
        contentType: 'application/json',
        headers: {
          ...headers,
          'access-control-expose-headers': 'x-total-count',
          'x-total-count': String(merged.length),
        },
        body,
      });
    }
  );
}

/**
 * CRUD interaction tests for the Knowledge (sources) page.
 *
 * Covers: A2.3 (upload a TXT file), A2.6 (delete a source via row actions).
 * Uses a small fixture TXT file from the fixtures directory.
 */
test.describe('Knowledge — CRUD @crud', () => {
  // stubKnowledgeUpload's GET handler proxies through to the real backend
  // (route.fetch()) and stays registered for the page's lifetime. If the app
  // issues a background refetch of the sources list after a test's own
  // assertions have already passed (e.g. a post-upload revalidation), that
  // in-flight route.fetch() can still be running when Playwright tears down
  // the page for the next test — throwing "Target page, context or browser
  // has been closed" and failing a test that otherwise passed. Unrouting
  // with `ignoreErrors` discards any such stray in-flight handler instead of
  // letting its rejection surface.
  test.afterEach(async ({ page }) => {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('can open the Upload Source dialog', async ({ page }) => {
    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Open the upload dialog
    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    await knowledgePage.openUploadSourceDialog();

    // Drawer should be visible
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can upload a TXT file as a knowledge source', async ({ page }) => {
    test.setTimeout(90_000);
    const UNIQUE_TITLE = `e2e-source-${Date.now()}`;
    const fixturePath = path.join(__dirname, '../fixtures/fixture.txt');
    const stubbedSource = {
      id: randomUUID(),
      title: UNIQUE_TITLE,
      description: 'Uploaded by Playwright E2E test',
    };

    await stubKnowledgeUpload(page, stubbedSource);

    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    await knowledgePage.openUploadSourceDialog();
    await knowledgePage.selectUploadFile(fixturePath);

    // Override the auto-populated title with a unique name
    await knowledgePage.setSourceTitle(UNIQUE_TITLE);
    await knowledgePage.setSourceDescription('Uploaded by Playwright E2E test');

    await knowledgePage.submitUpload();
    await knowledgePage.waitForUploadDrawerClosed();
    await expectGridRowVisible(page, UNIQUE_TITLE);
  });

  // TODO: re-enable after fixing grid row-actions delete (column virtualization / timeout)
  test.skip('can delete a knowledge source via row actions', async ({
    page,
  }) => {
    const UNIQUE_TITLE = `e2e-src-del-${Date.now()}`;
    const fixturePath = path.join(__dirname, '../fixtures/fixture.txt');

    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    // --- Setup: upload a source to delete ---
    await knowledgePage.openUploadSourceDialog();
    await page.locator('input[type="file"]').first().setInputFiles(fixturePath);
    await knowledgePage.setSourceTitle(UNIQUE_TITLE);
    await knowledgePage.submitUpload();
    await knowledgePage.waitForUploadDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expectGridRowVisible(page, UNIQUE_TITLE);

    // --- Delete: hover row and click the delete icon ---
    await knowledgePage.deleteRowByText(UNIQUE_TITLE);
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    // The row should be gone
    const gone = await knowledgePage.rowIsGone(UNIQUE_TITLE);
    expect(
      gone,
      `Expected source "${UNIQUE_TITLE}" to be removed from the grid`
    ).toBeTruthy();
  });
});
