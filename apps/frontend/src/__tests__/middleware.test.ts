/**
 * @jest-environment node
 *
 * Project deep-link switching (issue 2133) tests.
 *
 * The deep-link logic lives in `applyProjectDeepLink` in `src/proxy.ts` —
 * extracted from the legacy `src/middleware.ts` (removed when the repo
 * migrated to Next.js's `proxy.ts` pattern in #2183). The full `proxy()`
 * function's auth/session contract is covered by `proxy.test.ts`; this
 * suite pins down only the deep-link switching branch.
 *
 * Runs in the node environment because NextRequest/NextResponse need the
 * fetch-API globals (Request, Headers) that jest-environment-jsdom strips.
 */
import { NextRequest } from 'next/server';
import { applyProjectDeepLink } from '../proxy';
import { ACTIVE_PROJECT_COOKIE } from '../utils/active-project';

// Fixed UUIDs for deterministic tests. Both match the UUID pattern in
// proxy.ts so the validation branch is exercised honestly.
const TARGET_UUID = '12345678-1234-1234-1234-123456789abc';
const OTHER_UUID = '87654321-4321-4321-4321-210987654321';

/**
 * Build a NextRequest as proxy() would receive it: a path, optional
 * `?project_id=` query param, and optional incoming cookies.
 *
 * Cookies are set via the `Cookie` request header (the same wire format
 * the browser sends) rather than via a cookies API so we exercise the
 * real NextRequest parsing path.
 */
function buildRequest(
  path: string,
  opts: {
    project_id?: string;
    cookies?: Record<string, string>;
  } = {}
): NextRequest {
  const url = new URL(path, 'http://localhost:3000');
  if (opts.project_id !== undefined) {
    url.searchParams.set('project_id', opts.project_id);
  }
  const headers = new Headers();
  if (opts.cookies) {
    const cookieHeader = Object.entries(opts.cookies)
      .map(([k, v]) => `${k}=${v}`)
      .join('; ');
    if (cookieHeader) headers.set('cookie', cookieHeader);
  }
  return new NextRequest(url, { headers });
}

describe('applyProjectDeepLink — project deep-link switching (issue 2133)', () => {
  describe('no-op branches (returns null)', () => {
    it('returns null when project_id is absent', () => {
      const req = buildRequest('/test-runs/abc');
      const res = applyProjectDeepLink(req);
      expect(res).toBeNull();
      // Request cookies must be untouched.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBeUndefined();
    });

    it('returns null when project_id is not a UUID', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: 'not-a-uuid',
      });
      const res = applyProjectDeepLink(req);
      expect(res).toBeNull();
      // A malformed value must NOT overwrite an existing cookie.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBeUndefined();
    });

    it('returns null when project_id matches the current cookie', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: TARGET_UUID },
      });
      const res = applyProjectDeepLink(req);
      expect(res).toBeNull();
      // No mutation needed when already on the target project.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(TARGET_UUID);
    });

    it('does not clobber an existing different project cookie when project_id is malformed', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: 'literally-anything',
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      const res = applyProjectDeepLink(req);
      expect(res).toBeNull();
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(OTHER_UUID);
    });
  });

  describe('cookie switching (returns NextResponse with Set-Cookie)', () => {
    it('sets the project cookie on the response when no current cookie exists', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
      });
      const res = applyProjectDeepLink(req);
      expect(res).not.toBeNull();
      const setCookie = res!.headers.get('set-cookie');
      expect(setCookie).not.toBeNull();
      expect(setCookie).toContain(`${ACTIVE_PROJECT_COOKIE}=${TARGET_UUID}`);
      expect(setCookie).toMatch(/Path=\/(?:;|$)/i);
      expect(setCookie).toMatch(/SameSite=Lax/i);
      // max-age must match writeActiveProjectId (1 year) so the server-
      // and client-side writes produce identical cookies.
      expect(setCookie).toMatch(/Max-Age=31536000/i);
    });

    it('sets the project cookie on the response when a different cookie exists', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      const res = applyProjectDeepLink(req);
      expect(res).not.toBeNull();
      const setCookie = res!.headers.get('set-cookie');
      expect(setCookie).not.toBeNull();
      expect(setCookie).toContain(`${ACTIVE_PROJECT_COOKIE}=${TARGET_UUID}`);
      // The OLD value must NOT also be present.
      expect(setCookie).not.toContain(`${ACTIVE_PROJECT_COOKIE}=${OTHER_UUID}`);
    });
  });

  describe('C1 regression — request cookie propagation', () => {
    // The whole point of the deep-link switch is that the FIRST server-
    // rendered fetch sees the new project_id. `response.cookies.set()`
    // only adds a `Set-Cookie` response header (browser stores it for
    // the NEXT navigation). Server components' `cookies()` reads the
    // CURRENT request's `Cookie` header — so the helper must also mutate
    // the incoming request's cookies via `request.cookies.set()`.
    //
    // Without this fix the deep-linked page would still 404 on first hit
    // because the server fetch runs with the OLD project_id cookie.
    it('mutates the INCOMING request cookies so downstream cookies() sees the new project_id', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      // Pre-condition: cookie starts as OTHER_UUID.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(OTHER_UUID);
      applyProjectDeepLink(req);
      // Post-condition: cookie on the REQUEST is now TARGET_UUID.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(TARGET_UUID);
    });

    it('mutates the request Cookie header (downstream reads via headers, not cookies API)', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      applyProjectDeepLink(req);
      // The Cookie header itself must reflect the new value — this is
      // what gets forwarded via NextResponse.next({ request: { headers } }).
      const cookieHeader = req.headers.get('cookie') ?? '';
      expect(cookieHeader).toContain(`${ACTIVE_PROJECT_COOKIE}=${TARGET_UUID}`);
      expect(cookieHeader).not.toContain(
        `${ACTIVE_PROJECT_COOKIE}=${OTHER_UUID}`
      );
    });

    it('also sets the response Set-Cookie for browser persistence (both paths covered)', () => {
      const req = buildRequest('/test-runs/abc', {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      const res = applyProjectDeepLink(req);
      // C1 fix: request-side mutation.
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(TARGET_UUID);
      // Browser persistence: response-side Set-Cookie.
      expect(res!.headers.get('set-cookie')).toContain(
        `${ACTIVE_PROJECT_COOKIE}=${TARGET_UUID}`
      );
    });
  });

  describe('matcher coverage', () => {
    // The matcher in proxy.ts covers all non-static paths; the deep-link
    // helper itself is URL-agnostic and would handle each project-scoped
    // detail path identically. These tests document that intent.
    it.each([
      '/test-runs/abc',
      '/test-sets/abc',
      '/tasks/abc',
      '/test-runs/abc/compare', // trailing sub-route
    ])('switches project on matched path %s', path => {
      const req = buildRequest(path, {
        project_id: TARGET_UUID,
        cookies: { [ACTIVE_PROJECT_COOKIE]: OTHER_UUID },
      });
      const res = applyProjectDeepLink(req);
      expect(res).not.toBeNull();
      expect(res!.headers.get('set-cookie')).toContain(
        `${ACTIVE_PROJECT_COOKIE}=${TARGET_UUID}`
      );
      expect(req.cookies.get(ACTIVE_PROJECT_COOKIE)?.value).toBe(TARGET_UUID);
    });
  });
});
