import { NextResponse, type NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { auth } from './auth';
import {
  DEFAULT_AUTHENTICATED_PATH,
  isPublicPath,
  ONBOARDING_PATH,
} from './constants/paths';
import {
  getServerBackendUrl,
  shouldUseSecureCookies,
} from './utils/url-resolver';

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

// Helper function to verify token with backend
async function verifySessionWithBackend(sessionToken: string) {
  if (isLocalE2EVerificationEnabled()) {
    return verifySessionLocally(sessionToken);
  }

  try {
    const response = await fetch(`${getServerBackendUrl()}/auth/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ session_token: sessionToken }),
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();
    return data.authenticated && data.user;
  } catch (_error) {
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

export async function proxy(request: NextRequest) {
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

  // If not public, check for session
  try {
    // Get session token from request
    const sessionToken = await getSessionTokenFromRequest(request);
    if (!sessionToken) {
      // For users accessing protected routes without any authentication,
      // redirect to home page which has the unified login experience
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('return_to', pathname);
      homeUrl.searchParams.set('session_expired', 'true');
      return NextResponse.redirect(homeUrl);
    }

    // Verify session token with backend
    const isValidBackendSession = await verifySessionWithBackend(sessionToken);
    if (!isValidBackendSession) {
      // For users with expired/invalid sessions (they were previously authenticated),
      // redirect to home page with session clearing and expired flag
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      homeUrl.searchParams.set('force_logout', 'true');
      return await createSessionClearingResponse(homeUrl, true, sessionToken); // Call backend logout with session token
    }

    // Get session data from auth
    const session = await auth();
    if (!session?.user?.organization_id && pathname !== ONBOARDING_PATH) {
      return NextResponse.redirect(new URL(ONBOARDING_PATH, request.url));
    }

    if (pathname === ONBOARDING_PATH && session?.user?.organization_id) {
      return NextResponse.redirect(
        new URL(DEFAULT_AUTHENTICATED_PATH, request.url)
      );
    }

    return NextResponse.next();
  } catch (error: unknown) {
    const err = error instanceof Error ? error : new Error(String(error));

    if (err.message?.includes('UntrustedHost')) {
      // For untrusted host errors, redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(
        homeUrl,
        true,
        (await getSessionTokenFromRequest(request)) || undefined
      ); // Call backend logout
    }

    const isJWTError =
      err.message?.includes('JWTSessionError') ||
      err.name === 'JWTSessionError' ||
      (err.cause as Error)?.message?.includes('no matching decryption secret');

    if (isJWTError) {
      // For JWT errors (expired/invalid sessions), redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(
        homeUrl,
        true,
        (await getSessionTokenFromRequest(request)) || undefined
      ); // Call backend logout
    }

    throw error;
  }
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
