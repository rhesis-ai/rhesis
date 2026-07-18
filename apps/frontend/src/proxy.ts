import { NextResponse, type NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';
import {
  applyRefreshedSessionCookie,
  decodeJwtUser,
  getFreshAccessToken,
} from './auth';
import {
  DEFAULT_AUTHENTICATED_PATH,
  isPublicPath,
  ONBOARDING_PATH,
} from './constants/paths';
import {
  getServerBackendUrl,
  shouldUseSecureCookies,
} from './utils/url-resolver';
import { ACTIVE_PROJECT_COOKIE } from './utils/active-project';

const decodeBase64 =
  globalThis.atob ??
  ((value: string) => Buffer.from(value, 'base64').toString('binary'));

/** Decode a JWT payload segment without Node `Buffer` (middleware runs on Edge). */
function decodeBase64Url(value: string): string {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
  const padLen = (4 - (base64.length % 4)) % 4;
  const padded = padLen ? `${base64}${'='.repeat(padLen)}` : base64;
  return decodeBase64(padded);
}

/** Unsigned JWT verification is allowed only for local Playwright (E2E_NO_DOCKER). */
function isLocalE2EVerificationEnabled(): boolean {
  return (
    process.env.E2E_NO_DOCKER === '1' &&
    process.env.NODE_ENV !== 'production' &&
    (process.env.FRONTEND_ENV === 'development' ||
      process.env.FRONTEND_ENV === 'test' ||
      !process.env.FRONTEND_ENV)
  );
}

/** Local JWT check for Playwright runs without a backend (E2E_NO_DOCKER=1). */
function verifySessionLocally(sessionToken: string): boolean {
  try {
    if (!sessionToken.includes('.') || sessionToken.split('.').length !== 3) {
      return false;
    }

    const [, payloadB64] = sessionToken.split('.');
    const payload = JSON.parse(decodeBase64Url(payloadB64)) as {
      exp?: number;
      user?: { organization_id?: string | null };
    };

    const exp = payload.exp;
    if (!exp || Math.floor(Date.now() / 1000) >= exp) {
      return false;
    }

    return Boolean(payload.user?.organization_id);
  } catch {
    return false;
  }
}

// Helper function to get the backend access token from the request.
// The session cookie is an encrypted JWE, so it must be decrypted with the
// NextAuth secret (getToken) rather than parsed as plaintext.
async function getSessionTokenFromRequest(
  request: NextRequest
): Promise<string | null> {
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
    cookieName: 'next-auth.session-token',
  });
  return (token?.session_token as string | undefined) ?? null;
}

// Helper function to create a response that clears session cookies
async function createSessionClearingResponse(
  url: URL,
  shouldCallBackendLogout: boolean = false,
  sessionToken?: string
): Promise<NextResponse> {
  const response = NextResponse.redirect(url);

  // If requested, call backend logout first to clear server-side session
  if (shouldCallBackendLogout) {
    try {
      const logoutUrl = new URL('/auth/logout', getServerBackendUrl());
      if (sessionToken) {
        logoutUrl.searchParams.set('session_token', sessionToken);
      }

      await fetch(logoutUrl.toString(), {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      });
    } catch (_error) {
      // Continue with frontend cleanup even if backend fails
    }
  }

  // List of cookies to clear
  const cookiesToClear = [
    'next-auth.session-token',
    'next-auth.csrf-token',
    'next-auth.callback-url',
    'next-auth.pkce.code-verifier',
    'next-auth.pkce.state',
    'session',
    'authjs.session-token',
    'authjs.csrf-token',
    'authjs.callback-url',
    '__Host-next-auth.csrf-token',
    '__Secure-next-auth.callback-url',
    '__Secure-next-auth.session-token',
    // Additional possible cookie variations
    'next-auth.state',
    'authjs.state',
    'next-auth.nonce',
    'authjs.nonce',
  ];

  // Clear each cookie
  cookiesToClear.forEach(name => {
    // Delete the cookie (default behavior)
    response.cookies.delete(name);

    // Clear cookies for current hostname only (no cross-environment clearing).
    // Derive the secure flag from the same source used when the cookie is set
    // (auth.ts), so the clear matches the set and reliably overwrites it.
    response.cookies.set(name, '', {
      path: '/',
      secure: shouldUseSecureCookies(),
      sameSite: 'lax',
      maxAge: 0,
      expires: new Date(0),
    });
  });

  return response;
}

// UUID pattern for `?project_id=<uuid>` deep links from backend email
// notifications. See `applyProjectDeepLink` below.
const UUID_PATTERN =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

// Cookie max-age must match writeActiveProjectId() so server- and
// client-side writes produce identical cookies (no shadowing).
const PROJECT_COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

/**
 * Proactively switch the active project when a project-scoped detail page is
 * reached via a deep link carrying `?project_id=<uuid>`.
 *
 * Backend email notifications thread the entity's owning project_id into
 * every project-scoped deep link (see issue 2133). Without this switch, the
 * target page's server component would fetch with the currently selected
 * project's cookie, 404 against the project-scoped API, and fall through to
 * `notFound()` before any client-side switcher could run.
 *
 * Running here — before the auth/session checks — lets us set the
 * `rh_active_project_id` cookie so `getServerActiveProjectId()` returns the
 * owning project on the very first server-rendered fetch. Auth still runs
 * afterwards on the (now project-correct) request.
 *
 * Returns `null` when no switching is needed so the caller can fall through
 * to the rest of the proxy logic.
 */
export function applyProjectDeepLink(
  request: NextRequest
): NextResponse | null {
  const projectId = request.nextUrl.searchParams.get('project_id');

  // No project_id in URL — normal navigation, no-op.
  if (!projectId) {
    return null;
  }

  // Reject malformed project_id — don't blindly trust a query param.
  // A non-UUID value would otherwise overwrite the cookie with garbage and
  // break the user's session.
  if (!UUID_PATTERN.test(projectId)) {
    return null;
  }

  const currentProjectId = request.cookies.get(ACTIVE_PROJECT_COOKIE)?.value;

  // Already on the correct project — no-op, avoids a Set-Cookie header on
  // every intra-project navigation that happens to carry ?project_id.
  if (currentProjectId === projectId) {
    return null;
  }

  // Mutate the INCOMING request's Cookie header FIRST.
  //
  // `response.cookies.set()` only adds a `Set-Cookie` response header —
  // the browser stores it for the NEXT navigation, but `cookies()` from
  // `next/headers` reads the CURRENT request's `Cookie` header, which is
  // unchanged. The server component on this same request would still see
  // the OLD project_id cookie and 404 against the project-scoped API.
  //
  // `NextRequest.cookies` is a `RequestCookies` whose `set()` mutates the
  // underlying `Cookie` header on `request.headers`. Then we forward that
  // modified headers object via `NextResponse.next({ request: { headers } })`,
  // which is how middleware propagates header changes to downstream server
  // components in a single request (no extra round-trip, no 404 flash).
  //
  // See: https://nextjs.org/docs/app/api-reference/functions/next-request#cookies
  request.cookies.set(ACTIVE_PROJECT_COOKIE, projectId);

  const response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  // ALSO set on the response so the browser persists it for future
  // navigations (otherwise the cookie would only live for this single
  // request and the next navigation would lose the project switch).
  response.cookies.set(ACTIVE_PROJECT_COOKIE, projectId, {
    path: '/',
    maxAge: PROJECT_COOKIE_MAX_AGE,
    sameSite: 'lax',
  });

  return response;
}

export async function proxy(request: NextRequest) {
  // Apply project deep-link switching before auth/session checks so the
  // first server-rendered fetch sees the correct project. Auth still runs
  // on the (now project-correct) request via the fall-through below.
  const deepLinkResponse = applyProjectDeepLink(request);
  if (deepLinkResponse) {
    return deepLinkResponse;
  }

  const pathname = request.nextUrl.pathname;

  // At the top of the middleware function, after pathname declaration
  const isPostLogout =
    request.nextUrl.searchParams.get('post_logout') === 'true';
  const _isSessionExpired =
    request.nextUrl.searchParams.get('session_expired') === 'true';

  // Prevent redirect loops by always allowing access to signin page
  if (pathname.startsWith('/auth/signin')) {
    // If this is a post-logout redirect, force return_to to root
    if (isPostLogout) {
      const signInUrl = new URL('/auth/signin', request.url);
      signInUrl.searchParams.set('return_to', '/');
      return await createSessionClearingResponse(signInUrl); // No backend logout needed (already logged out)
    }
    return NextResponse.next();
  }

  // Allow the logout page to function without auth checks
  if (pathname.startsWith('/auth/signout')) {
    return NextResponse.next();
  }

  // Allow public paths without auth checks
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Allow onboarding path without organization check
  if (pathname === ONBOARDING_PATH) {
    // Still check for auth though
  }

  // If not public, check for session.
  // Get the (possibly stale) access token from the session cookie first —
  // a failed refresh below still needs it to pass to the backend logout
  // call. getToken() returns null (never throws) for a missing, corrupt, or
  // undecryptable cookie, so no JWT-error handling is needed around this.
  const sessionToken = await getSessionTokenFromRequest(request);
  if (!sessionToken) {
    // For users accessing protected routes without any authentication,
    // redirect to home page which has the unified login experience
    const homeUrl = new URL('/', request.url);
    homeUrl.searchParams.set('return_to', pathname);
    homeUrl.searchParams.set('session_expired', 'true');
    return NextResponse.redirect(homeUrl);
  }

  // E2E-no-docker seeds a fake token that cannot be refreshed (there's no
  // backend to refresh against). Keep this as a local, non-network check
  // exactly as before.
  if (isLocalE2EVerificationEnabled()) {
    if (!verifySessionLocally(sessionToken)) {
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      homeUrl.searchParams.set('force_logout', 'true');
      return await createSessionClearingResponse(homeUrl, true, sessionToken);
    }
  }

  // Resolve a fresh access token via the SAME helper the /api/backend proxy
  // route uses — not via auth(). If the access token is stale this
  // transparently refreshes (coalesced across concurrent requests) before
  // returning, so a merely-expired-but-refreshable token never reaches the
  // check below as "invalid". Crucially, unlike auth(), it hands back the
  // re-encoded session cookie so this middleware can PERSIST the refresh:
  // the zero-arg auth() form discards Auth.js's Set-Cookie (it takes the
  // RSC branch internally), which left the cookie's access token frozen and
  // forced every subsequent request to refresh again. And unlike the
  // auth(handler) wrapper form, nothing here re-sets the session cookie
  // after createSessionClearingResponse — the wrapper appends Auth.js's
  // re-encoded cookie AFTER the handler's headers, which would resurrect
  // the session on the exact branch that must clear it.
  const { accessToken, refreshedCookie } = await getFreshAccessToken(request);

  if (!accessToken) {
    // The cookie existed but couldn't be resolved to a usable token — a
    // genuine refresh failure (revoked/expired refresh token). This is the
    // same signal useSessionGuard reacts to client-side; here we do the
    // equivalent for the initial page request.
    const homeUrl = new URL('/', request.url);
    homeUrl.searchParams.set('session_expired', 'true');
    homeUrl.searchParams.set('force_logout', 'true');
    return await createSessionClearingResponse(homeUrl, true, sessionToken);
  }

  const organizationId = decodeJwtUser(accessToken)?.organization_id;

  let response: NextResponse;
  if (!organizationId && pathname !== ONBOARDING_PATH) {
    response = NextResponse.redirect(new URL(ONBOARDING_PATH, request.url));
  } else if (pathname === ONBOARDING_PATH && organizationId) {
    response = NextResponse.redirect(
      new URL(DEFAULT_AUTHENTICATED_PATH, request.url)
    );
  } else {
    response = NextResponse.next();
  }

  // Persist the refreshed session cookie (no-op if no refresh happened) so
  // the next request reads a current token instead of re-refreshing.
  applyRefreshedSessionCookie(response, refreshedCookie);
  return response;
}

// Update the matcher configuration - catch everything except static files
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files
     */
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$|.*\\.jpg$|.*\\.jpeg$|.*\\.gif$|.*\\.svg$|.*\\.ico$|.*\\.css$|.*\\.js$).*)',
  ],
};
