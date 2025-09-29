import { NextResponse, type NextRequest } from 'next/server';
import { auth } from './auth';
import { isPublicPath, ONBOARDING_PATH } from './constants/paths';
import { getServerBackendUrl } from './utils/url-resolver';

// Helper function to verify token with backend
async function verifySessionWithBackend(sessionToken: string) {
  try {
    const response = await fetch(
      `${getServerBackendUrl()}/auth/verify?session_token=${sessionToken}`,
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    if (!response.ok) {
      return false;
    }

    const data = await response.json();
    return data.authenticated && data.user;
  } catch (error) {
    console.error('Backend session verification failed:', error);
    return false;
  }
}

// Helper function to get session token from request
function getSessionTokenFromRequest(request: NextRequest): string | null {
  const sessionCookie = request.cookies.get('next-auth.session-token');
  if (!sessionCookie?.value) return null;

  const cookieValue = sessionCookie.value;

  // Try to parse as JSON first (NextAuth.js stores session data as JSON)
  try {
    const sessionData = JSON.parse(cookieValue);
    // Extract the actual JWT token from the session data
    if (
      sessionData &&
      typeof sessionData === 'object' &&
      sessionData.session_token
    ) {
      return sessionData.session_token;
    }
  } catch (error) {
    // If JSON parsing fails, it might be a direct JWT token
    console.log(
      '[WARNING] [DEBUG] Session cookie is not JSON, treating as direct token'
    );
  }

  // If it's not JSON or doesn't have session_token field, return as is
  // This handles cases where the token is stored directly
  return cookieValue;
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
      console.log(
        '🟠 [DEBUG] Middleware calling backend logout for session expiration'
      );
      const logoutUrl = new URL('/auth/logout', process.env.BACKEND_URL);
      if (sessionToken) {
        logoutUrl.searchParams.set('session_token', sessionToken);
      }

      await fetch(logoutUrl.toString(), {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      });
      console.log('🟠 [DEBUG] Backend logout completed in middleware');
    } catch (error) {
      console.warn(
        '🟠 [DEBUG] Backend logout failed in middleware (continuing with frontend cleanup):',
        error
      );
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

    // For production environment, also set expired cookies with various domain configurations
    if (process.env.FRONTEND_ENV === 'production') {
      // Clear with specific domain
      response.cookies.set(name, '', {
        domain: 'rhesis.ai',
        path: '/',
        secure: true,
        sameSite: 'lax',
        maxAge: 0,
        expires: new Date(0),
      });

      // Clear with leading dot domain for broader coverage
      response.cookies.set(name, '', {
        domain: '.rhesis.ai',
        path: '/',
        secure: true,
        sameSite: 'lax',
        maxAge: 0,
        expires: new Date(0),
      });
    } else {
      // For development, ensure cookies are cleared
      response.cookies.set(name, '', {
        path: '/',
        maxAge: 0,
        expires: new Date(0),
      });
    }
  });

  return response;
}

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  console.log('🟠 [DEBUG] Middleware called for pathname:', pathname);

  // At the top of the middleware function, after pathname declaration
  const isPostLogout =
    request.nextUrl.searchParams.get('post_logout') === 'true';
  const isSessionExpired =
    request.nextUrl.searchParams.get('session_expired') === 'true';

  console.log(
    '🟠 [DEBUG] Is post logout:',
    isPostLogout,
    'Is session expired:',
    isSessionExpired
  );

  // Prevent redirect loops by always allowing access to signin page
  if (pathname.startsWith('/auth/signin')) {
    console.log('🟠 [DEBUG] Auth signin path detected');
    // If this is a post-logout redirect, force return_to to root
    if (isPostLogout) {
      console.log('🟠 [DEBUG] Post logout redirect, clearing session cookies');
      const signInUrl = new URL('/auth/signin', request.url);
      signInUrl.searchParams.set('return_to', '/');
      return await createSessionClearingResponse(signInUrl); // No backend logout needed (already logged out)
    }
    return NextResponse.next();
  }

  // Allow the logout page to function without auth checks
  if (pathname.startsWith('/auth/signout')) {
    console.log('🟠 [DEBUG] Auth signout path detected, allowing access');
    return NextResponse.next();
  }

  // Allow public paths without auth checks
  if (isPublicPath(pathname)) {
    console.log('🟠 [DEBUG] Public path detected, allowing access');
    return NextResponse.next();
  }

  // Allow onboarding path without organization check
  if (pathname === ONBOARDING_PATH) {
    // Still check for auth though
    console.log('[AUTH] Onboarding path detected, checking auth only...');
  }

  // If not public, check for session
  console.log('[SECURE] Protected path detected, checking session...');
  try {
    // Get session token from request
    const sessionToken = getSessionTokenFromRequest(request);
    if (!sessionToken) {
      console.log('[ERROR] No session token found');
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
      console.log(
        '[ERROR] Backend session validation failed - clearing all session data'
      );
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
      console.log(
        '[WARNING] No organization_id found, redirecting to onboarding'
      );
      return NextResponse.redirect(new URL(ONBOARDING_PATH, request.url));
    }

    if (pathname === ONBOARDING_PATH && session?.user?.organization_id) {
      console.log(
        '[WARNING] User already has organization, redirecting to dashboard'
      );
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    console.log('[SUCCESS] Valid session found');
    return NextResponse.next();
  } catch (error: any) {
    const err = error as Error;

    console.log('[ALERT] Auth Error in middleware:', {
      type: typeof err,
      name: err.name,
      message: err.message,
      cause: err.cause,
      stack: err.stack,
    });

    if (err.message?.includes('UntrustedHost')) {
      console.log('[ERROR] UntrustedHost error detected');
      // For untrusted host errors, redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(
        homeUrl,
        true,
        getSessionTokenFromRequest(request) || undefined
      ); // Call backend logout
    }

    const isJWTError =
      err.message?.includes('JWTSessionError') ||
      err.name === 'JWTSessionError' ||
      (err.cause as Error)?.message?.includes('no matching decryption secret');

    if (isJWTError) {
      console.log('[ERROR] JWT Session Error detected');
      // For JWT errors (expired/invalid sessions), redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(
        homeUrl,
        true,
        getSessionTokenFromRequest(request) || undefined
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
