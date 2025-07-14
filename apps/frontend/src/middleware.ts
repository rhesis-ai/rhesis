import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { auth } from './auth'
import { isPublicPath, ONBOARDING_PATH } from './constants/paths'

// Helper function to verify token with backend
async function verifySessionWithBackend(sessionToken: string) {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/verify?session_token=${sessionToken}`,
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
    if (sessionData && typeof sessionData === 'object' && sessionData.session_token) {
      return sessionData.session_token;
    }
  } catch (error) {
    // If JSON parsing fails, it might be a direct JWT token
    console.log('⚠️ [DEBUG] Session cookie is not JSON, treating as direct token');
  }
  
  // If it's not JSON or doesn't have session_token field, return as is
  // This handles cases where the token is stored directly
  return cookieValue;
}

// Helper function to create a response that clears session cookies
function createSessionClearingResponse(url: URL): NextResponse {
  const response = NextResponse.redirect(url);
  
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
  ];

  // Clear each cookie
  cookiesToClear.forEach(name => {
    // Delete the cookie
    response.cookies.delete(name);
    
    // For production environment, also set an expired cookie with domain
    if (process.env.NODE_ENV === 'production') {
      response.cookies.set(name, '', {
        domain: 'rhesis.ai',
        path: '/',
        secure: true,
        sameSite: 'lax',
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
  
  console.log('🟠 [DEBUG] Is post logout:', isPostLogout);

  // Prevent redirect loops by always allowing access to signin page
  if (pathname.startsWith('/auth/signin')) {
    console.log('🟠 [DEBUG] Auth signin path detected');
    // If this is a post-logout redirect, force return_to to root
    if (isPostLogout) {
      console.log('🟠 [DEBUG] Post logout redirect, clearing session cookies');
      const signInUrl = new URL('/auth/signin', request.url);
      signInUrl.searchParams.set('return_to', '/');
      return createSessionClearingResponse(signInUrl);
    }
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
      // redirect to signin with return_to parameter for seamless experience
      const signInUrl = new URL('/auth/signin', request.url);
      signInUrl.searchParams.set('return_to', pathname);
      return NextResponse.redirect(signInUrl);
    }

    // Verify session token with backend
    const isValidBackendSession = await verifySessionWithBackend(sessionToken);
    if (!isValidBackendSession) {
      console.log('❌ Backend session validation failed');
      // For users with expired/invalid sessions (they were previously authenticated),
      // redirect to home page to complete the signout flow
      return createSessionClearingResponse(new URL('/', request.url));
    }

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
      return createSessionClearingResponse(new URL('/', request.url));
    }
    
    const isJWTError = err.message?.includes('JWTSessionError') || 
                      err.name === 'JWTSessionError' ||
                      (err.cause as Error)?.message?.includes('no matching decryption secret');
    
    if (isJWTError) {
      console.log('❌ JWT Session Error detected');
      // For JWT errors (expired/invalid sessions), redirect to home page with session clearing
      return createSessionClearingResponse(new URL('/', request.url));
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
