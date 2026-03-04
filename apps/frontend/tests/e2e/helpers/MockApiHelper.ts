import { type Page } from '@playwright/test';

/**
 * Helper class for intercepting backend API calls in E2E tests.
 *
 * The Rhesis frontend calls http://localhost:8080/api/v1/* via native fetch.
 * Playwright's page.route() intercepts these before they leave the browser,
 * allowing tests to run deterministically without a live backend.
 *
 * List endpoints return a flat JSON array; the total count is carried in
 * the x-total-count response header (consumed by fetchPaginated()).
 */
export class MockApiHelper {
  constructor(private readonly page: Page) {}

  /**
   * Mock a list (GET) endpoint to return the given fixture data.
   * The apiPath should match the backend path, e.g. '/test_sets' or '/tests'.
   */
  async mockList(
    apiPath: string,
    data: Record<string, unknown>[],
    totalCount?: number
  ) {
    await this.page.route(`**/api/v1${apiPath}**`, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'x-total-count': String(totalCount ?? data.length),
          'access-control-expose-headers': 'x-total-count',
        },
        body: JSON.stringify(data),
      })
    );
  }

  /**
   * Mock an endpoint to return an HTTP error response.
   * Useful for testing that pages render a proper error UI instead of crashing.
   */
  async mockError(apiPath: string, status: 401 | 404 | 500) {
    await this.page.route(`**/api/v1${apiPath}**`, route =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Simulated error' }),
      })
    );
  }

  /**
   * Mock a single detail (GET by ID) endpoint.
   * Uses an exact path match to avoid colliding with list endpoint wildcards.
   */
  async mockDetail(apiPath: string, id: string, data: Record<string, unknown>) {
    await this.page.route(`**/api/v1${apiPath}/${id}`, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(data),
      })
    );
  }

  /**
   * Mock all list-style endpoints simultaneously (useful for pages that call
   * multiple APIs on mount, e.g. dashboard).
   */
  async mockAllLists(paths: string[], data: Record<string, unknown>[] = []) {
    for (const path of paths) {
      await this.mockList(path, data);
    }
  }
}
