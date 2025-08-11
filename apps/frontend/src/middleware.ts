import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { auth } from './auth'
import { isPublicPath, ONBOARDING_PATH } from './constants/paths'

// Helper function to verify token with backend
async function verifySessionWithBackend(sessionToken: string) {
  try {
    // Since we're running in Docker containers, always use the container name
    const apiUrl = 'http://backend:8080';
    
    console.log('🟠 [DEBUG] Using API URL for verification:', apiUrl);
    
    const response = await fetch(
      `${apiUrl}/auth/verify?session_token=${sessionToken}`,
      {
        headers: {
          Accept: 'application/json',
        },
        // Add timeout for Docker environment
        signal: AbortSignal.timeout(5000), // 5 second timeout
      }
    );

    if (!response.ok) {
      console.log('🟠 [DEBUG] Backend verification failed with status:', response.status);
      return false;
    }

    const data = await response.json();
    return data.authenticated && data.user;
  } catch (error) {
    console.error('🟠 [DEBUG] Backend session verification failed:', error);
    return false;
  }
}

// Helper function to get session token from request
function getSessionTokenFromRequest(request: NextRequest): string | null {
  // Try multiple possible cookie names
  const possibleCookies = [
    'next-auth.session-token',
    'session',
    'authjs.session-token',
    '__Secure-next-auth.session-token'
  ];
  
  let sessionCookie = null;
  for (const cookieName of possibleCookies) {
    sessionCookie = request.cookies.get(cookieName);
    if (sessionCookie?.value) {
      console.log('🟠 [DEBUG] Found session cookie:', cookieName);
      break;
    }
  }
  
  if (!sessionCookie?.value) {
    console.log('🟠 [DEBUG] No session cookie found');
    return null;
  }
  
  const cookieValue = sessionCookie.value;
  
  // Try to parse as JSON first (NextAuth.js stores session data as JSON)
  try {
    const sessionData = JSON.parse(cookieValue);
    // Extract the actual JWT token from the session data
    if (sessionData && typeof sessionData === 'object' && sessionData.session_token) {
      console.log('🟠 [DEBUG] Extracted session_token from JSON');
      return sessionData.session_token;
    }
  } catch (error) {
    // If JSON parsing fails, it might be a direct JWT token
    console.log('🟠 [DEBUG] Session cookie is not JSON, treating as direct token');
  }
  
  // If it's not JSON or doesn't have session_token field, return as is
  // This handles cases where the token is stored directly
  return cookieValue;
}

// Helper function to create a response that clears session cookies
async function createSessionClearingResponse(url: URL, shouldCallBackendLogout: boolean = false, sessionToken?: string): Promise<NextResponse> {
  const response = NextResponse.redirect(url);
  
  // If requested, call backend logout first to clear server-side session
  if (shouldCallBackendLogout) {
    try {
      console.log('🟠 [DEBUG] Middleware calling backend logout for session expiration');
      // Since we're running in Docker containers, always use the container name
      const apiUrl = 'http://backend:8080';
      const logoutUrl = new URL('/auth/logout', apiUrl);
      if (sessionToken) {
        logoutUrl.searchParams.set('session_token', sessionToken);
      }
      
      const logoutResponse = await fetch(logoutUrl.toString(), {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        signal: AbortSignal.timeout(3000), // 3 second timeout
      });
      
      if (logoutResponse.ok) {
        console.log('🟠 [DEBUG] Backend logout completed in middleware');
      } else {
        console.warn('🟠 [DEBUG] Backend logout failed with status:', logoutResponse.status);
      }
    } catch (error) {
      console.warn('🟠 [DEBUG] Backend logout failed in middleware (continuing with frontend cleanup):', error);
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
    if (process.env.NODE_ENV === 'production') {
      // Clear with specific domain
      response.cookies.set(name, '', {
        domain: 'rhesis.ai',
        path: '/',
        secure: true,
        sameSite: 'lax',
        maxAge: 0,
        expires: new Date(0)
      });
      
      // Clear with leading dot domain for broader coverage
      response.cookies.set(name, '', {
        domain: '.rhesis.ai',
        path: '/',
        secure: true,
        sameSite: 'lax',
        maxAge: 0,
        expires: new Date(0)
      });
    } else {
      // For development, ensure cookies are cleared
      response.cookies.set(name, '', {
        path: '/',
        maxAge: 0,
        expires: new Date(0)
      });
    }
  });

  return response;
}

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  
  console.log('🟠 [DEBUG] Middleware called for pathname:', pathname);
  
  // At the top of the middleware function, after pathname declaration
  const isPostLogout = request.nextUrl.searchParams.get('post_logout') === 'true';
  const isSessionExpired = request.nextUrl.searchParams.get('session_expired') === 'true';
  
  console.log('🟠 [DEBUG] Is post logout:', isPostLogout, 'Is session expired:', isSessionExpired);

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
    return NextResponse.next()
  }

  // Allow onboarding path without organization check
  if (pathname === ONBOARDING_PATH) {
    // Still check for auth though
    console.log('🔑 Onboarding path detected, checking auth only...')
  }

  // If not public, check for session
  console.log('🔒 Protected path detected, checking session...')
  try {
    // Get session token from request
    const sessionToken = getSessionTokenFromRequest(request);
    if (!sessionToken) {
      console.log('❌ No session token found');
      // For users accessing protected routes without any authentication,
      // redirect to home page which has the unified login experience
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('return_to', pathname);
      homeUrl.searchParams.set('session_expired', 'true');
      return NextResponse.redirect(homeUrl);
    }

    // Verify session token with backend
    console.log('🟠 [DEBUG] Verifying session token with backend...');
    const isValidBackendSession = await verifySessionWithBackend(sessionToken);
    if (!isValidBackendSession) {
      console.log('❌ Backend session validation failed - clearing all session data');
      // For users with expired/invalid sessions (they were previously authenticated),
      // redirect to home page with session clearing and expired flag
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      homeUrl.searchParams.set('force_logout', 'true');
      return await createSessionClearingResponse(homeUrl, true, sessionToken); // Call backend logout with session token
    }
    
    console.log('✅ Backend session validation successful');

    // Get session data from auth
    const session = await auth();
    if (!session?.user?.organization_id && pathname !== ONBOARDING_PATH) {
      console.log('⚠️ No organization_id found, redirecting to onboarding');
      return NextResponse.redirect(new URL(ONBOARDING_PATH, request.url));
    }

    if (pathname === ONBOARDING_PATH && session?.user?.organization_id) {
      console.log('⚠️ User already has organization, redirecting to dashboard');
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    console.log('✅ Valid session found');
    return NextResponse.next();
  } catch (error: any) {
    const err = error as Error;
    
    console.log('🚨 Auth Error in middleware:', {
      type: typeof err,
      name: err.name,
      message: err.message,
      cause: err.cause,
      stack: err.stack
    });
    
    if (err.message?.includes('UntrustedHost')) {
      console.log('❌ UntrustedHost error detected');
      // For untrusted host errors, redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(homeUrl, true, getSessionTokenFromRequest(request) || undefined); // Call backend logout
    }
    
    const isJWTError = err.message?.includes('JWTSessionError') || 
                      err.name === 'JWTSessionError' ||
                      (err.cause as Error)?.message?.includes('no matching decryption secret');
    
    if (isJWTError) {
      console.log('❌ JWT Session Error detected');
      // For JWT errors (expired/invalid sessions), redirect to home page with session clearing
      const homeUrl = new URL('/', request.url);
      homeUrl.searchParams.set('session_expired', 'true');
      return await createSessionClearingResponse(homeUrl, true, getSessionTokenFromRequest(request) || undefined); // Call backend logout
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
}
