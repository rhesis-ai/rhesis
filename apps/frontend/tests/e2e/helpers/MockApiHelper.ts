import { type Page, type Route, expect } from '@playwright/test';
import projectsFixture from '../fixtures/projects.json';

/**
 * Helper class for intercepting backend API calls in E2E tests.
 *
 * The Rhesis frontend calls the backend at `{API_BASE_URL}/resources` (and
 * optionally via `/api/v1/...` in local mock-server runs). Playwright's
 * page.route() intercepts these before they leave the browser.
 * allowing tests to run deterministically without a live backend.
 *
 * List endpoints return a flat JSON array; the total count is carried in
 * the x-total-count response header (consumed by fetchPaginated()).
 *
 * Route registration order matters: Playwright matches routes in LIFO order
 * (last registered = first matched). When both mockList() and mockDetail()
 * are used for the same resource, always call mockDetail() AFTER mockList()
 * so the more specific detail route takes priority.
 *
 * Patterns here match on bare resource paths (`/tokens`, `/behaviors`, …)
 * with no origin/host restriction, because the frontend's `API_BASE_URL`
 * varies across configurations (mock-backend, live backend, prod). A page
 * whose route happens to share its name with its own API resource (e.g. the
 * `/tokens` page and the `/tokens` list endpoint) would otherwise also match
 * the *page navigation* request itself — hijacking the page load and
 * replacing it with the mocked JSON body. All route registrations below go
 * through `routeApi()`, which excludes `resourceType() === 'document'`
 * requests (top-level navigations) so only actual API calls are mocked.
 */
export class MockApiHelper {
  constructor(private readonly page: Page) {}

  /**
   * Register a route, but only handle it for genuine API calls — never for
   * the top-level page navigation (`resourceType() === 'document'`), which
   * can otherwise collide with a bare resource path like `/tokens` or
   * `/behaviors` and hijack the page load itself. See class docstring.
   */
  private async routeApi(
    pattern: string | RegExp,
    handler: (route: Route) => unknown
  ) {
    await this.page.route(pattern, route => {
      if (route.request().resourceType() === 'document') {
        return route.fallback();
      }
      return handler(route);
    });
  }

  /**
   * Build a regex that matches only list-level requests for a given API path.
   * The pattern matches the path followed by an optional trailing slash and
   * end-of-path or a query string, but NOT additional path segments (which
   * would indicate a detail request).
   *
   * The trailing slash is required, not cosmetic: `BaseApiClient.fetchPaginated`
   * (used by every paginated list() method) always appends one — e.g.
   * `ProjectsClient.getProjects()` requests `/api/v1/projects/?skip=0&...`, not
   * `/api/v1/projects?skip=0&...`. Without it here, list-page tests silently
   * fall through to the real network and its 500/CORS failure gets rendered
   * as an error state instead of the mocked empty/populated one.
   *
   * e.g. /api/v1/tests  or  /api/v1/tests/  or  /api/v1/tests/?limit=100  → matched
   *      /api/v1/tests/some-uuid                                          → NOT matched
   */
  private listRoutePattern(apiPath: string): RegExp {
    const escaped = apiPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Optional /api/v1 prefix for mock-backend; live backend uses bare paths.
    return new RegExp(`(/api/v1)?${escaped}/?(\\?|$)`);
  }

  private jsonListResponse(
    data: Record<string, unknown>[],
    totalCount?: number
  ) {
    return {
      status: 200 as const,
      contentType: 'application/json',
      headers: {
        'x-total-count': String(totalCount ?? data.length),
        'access-control-expose-headers': 'x-total-count',
      },
      body: JSON.stringify(data),
    };
  }

  /**
   * Mock member projects used by ActiveProjectContext (layout project gate).
   * Must return at least one project so protected pages render past NoProjectAccess.
   */
  async mockMyProjects(
    data: Record<string, unknown>[] = projectsFixture as Record<
      string,
      unknown
    >[]
  ) {
    await this.routeApi('**/projects/mine**', route =>
      route.fulfill(this.jsonListResponse(data))
    );
  }

  /** Mock user settings fetch used when resolving the active project. */
  async mockUserSettings() {
    await this.routeApi('**/users/settings**', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ui: { theme: 'light' },
          models: {},
          notifications: {},
          default_project: { project_id: projectsFixture[0]?.id ?? null },
        }),
      })
    );
  }

  /** Standard layout mocks — call before navigating to any protected page. */
  async mockLayoutPrerequisites(
    projects: Record<string, unknown>[] = projectsFixture as Record<
      string,
      unknown
    >[]
  ) {
    await this.mockMyProjects(projects);
    await this.mockUserSettings();
  }

  /** Wait until ActiveProjectContext has loaded member projects. */
  async waitForProjectGate(timeout = 15_000) {
    await expect(this.page.getByText('No project access')).not.toBeVisible({
      timeout,
    });
  }

  /**
   * Mock a list (GET) endpoint to return the given fixture data.
   * The apiPath should match the backend path, e.g. '/test_sets' or '/tests'.
   * Uses a regex pattern that only matches the collection URL, not sub-resources.
   */
  async mockList(
    apiPath: string,
    data: Record<string, unknown>[],
    totalCount?: number
  ) {
    await this.routeApi(this.listRoutePattern(apiPath), route =>
      route.fulfill(this.jsonListResponse(data, totalCount))
    );
  }

  /**
   * Mock an endpoint to return an HTTP error response.
   * Useful for testing that pages render a proper error UI instead of crashing.
   * Uses the same regex as mockList() to avoid matching detail sub-paths.
   */
  async mockError(apiPath: string, status: 401 | 404 | 500) {
    await this.routeApi(this.listRoutePattern(apiPath), route =>
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
    const escaped = apiPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    await this.routeApi(
      new RegExp(`(/api/v1)?${escaped}/${id}(\\?|$)`),
      route =>
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

/** Assert a MUI DataGrid (or ARIA grid) is visible. */
export async function expectDataGridVisible(page: Page) {
  const grid = page.locator('.MuiDataGrid-root, [role="grid"]').first();
  await expect(grid).toBeVisible({ timeout: 15_000 });
}
