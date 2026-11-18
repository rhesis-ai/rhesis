import { NextRequest, NextResponse } from 'next/server';
import { applyRefreshedSessionCookie, getFreshAccessToken } from '@/auth';
import { isOAuthNavigation, proxyToBackend } from '@/utils/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * BFF proxy for all authenticated client API calls.
 *
 * The browser never holds a backend access token — client `BaseApiClient`
 * instances point at `/api/backend/*` (same origin) instead of the backend
 * directly, and this route injects `Authorization` server-side from the
 * httpOnly session cookie, refreshing it first if it's stale. This is what
 * makes the access token structurally invisible to browser JS: there is
 * nothing for a component's dependency array or query key to depend on.
 *
 * Fails closed (401) when there's no valid session rather than forwarding an
 * unauthenticated request to the backend, except for the backend's `/auth/*`
 * routes: the browser reaches sign-in, registration and OAuth only through here.
 *
 * This is also the ONE call site that can actually close the refresh loop:
 * as a route handler it's allowed to set cookies on its response, so when
 * `getFreshAccessToken()` performs a refresh, the updated cookie is applied
 * here — keeping `access_token_expires` current so the NEXT request doesn't
 * see a stale, already-past expiry and refresh again unnecessarily.
 */

/**
 * Fetch-Metadata CSRF guard. The proxy authenticates purely by cookie
 * (SameSite=Lax), and Lax still sends cookies on cross-site *top-level GET
 * navigations* — so without this check, a link to e.g.
 * `/api/backend/auth/logout` from any site would revoke the victim's
 * refresh-token family. Legitimate traffic is exclusively same-origin
 * `fetch()` from the app (`Sec-Fetch-Site: same-origin`) or direct
 * user-initiated requests (`none`); `same-site` (subdomains) and
 * `cross-site` are rejected for ALL methods. Browsers that don't send
 * Fetch-Metadata can't be distinguished on GET (navigations carry no
 * Origin header), so they fall back to an Origin check on unsafe methods
 * only — Lax already withholds cookies from cross-site non-GET, making
 * that the lower-risk gap.
 */
function isCrossSiteRequest(req: NextRequest): boolean {
  const secFetchSite = req.headers.get('sec-fetch-site');
  if (secFetchSite) {
    return secFetchSite !== 'same-origin' && secFetchSite !== 'none';
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const origin = req.headers.get('origin');
    return origin !== null && origin !== req.nextUrl.origin;
  }
  return false;
}

async function handle(req: NextRequest): Promise<NextResponse> {
  const backendPath = req.nextUrl.pathname.replace(/^\/api\/backend/, '');

  // OAuth/SSO logins arrive as cross-site navigations (the IdP's redirect, a
  // shared SSO link). They carry no session to inject, and the callback is
  // protected by the OAuth `state` check instead.
  if (isOAuthNavigation(req.method, backendPath)) {
    return proxyToBackend(req, { backendPath });
  }

  if (isCrossSiteRequest(req)) {
    return NextResponse.json(
      { error: 'Cross-site request rejected' },
      {
        status: 403,
      }
    );
  }

  const { accessToken, refreshedCookie } = await getFreshAccessToken({
    headers: req.headers,
  });
  if (!accessToken) {
    // Sign-in, registration, password reset and the like run before there is a
    // session; the backend decides which of its /auth routes allow that.
    if (backendPath.startsWith('/auth/')) {
      return proxyToBackend(req, { backendPath });
    }
    // `x-auth-origin: bff` marks this 401 as issued by the proxy itself
    // (no resolvable session) rather than by the backend rejecting a
    // presented token. `BaseApiClient` keys its "clear local state only,
    // don't revoke server-side" behavior off this header.
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401, headers: { 'x-auth-origin': 'bff' } }
    );
  }

  const response = await proxyToBackend(req, {
    backendPath,
    overrideHeaders: { authorization: `Bearer ${accessToken}` },
  });
  applyRefreshedSessionCookie(response, refreshedCookie);
  return response;
}

export function GET(req: NextRequest) {
  return handle(req);
}
export function POST(req: NextRequest) {
  return handle(req);
}
export function PUT(req: NextRequest) {
  return handle(req);
}
export function PATCH(req: NextRequest) {
  return handle(req);
}
export function DELETE(req: NextRequest) {
  return handle(req);
}
