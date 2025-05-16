import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { auth } from './auth'
import { PROTECTED_PATHS, isPublicPath, isSuperuserPath, ONBOARDING_PATH } from './constants/paths'

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  
  // At the top of the middleware function, after pathname declaration
  const isPostLogout = request.nextUrl.searchParams.get('post_logout') === 'true';

  // Prevent redirect loops by always allowing access to signin page
  if (pathname.startsWith('/auth/signin')) {
    // If this is a post-logout redirect, force return_to to root
    if (isPostLogout) {
      const signInUrl = new URL('/auth/signin', request.url);
      signInUrl.searchParams.set('return_to', '/');
      return NextResponse.redirect(signInUrl);
    }
    return NextResponse.next();
  }

  // Allow public paths without auth checks
  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  // Allow onboarding path without organization check
  if (pathname === ONBOARDING_PATH) {
    // Still check for auth though
    console.log('🔑 Onboarding path detected, checking auth only...')
  } else {
    // Check for superuser paths
    if (isSuperuserPath(pathname)) {
      console.log('🔒 Superuser path detected, checking session...')
    }
  }

  // If not public, check for session
  console.log('🔒 Protected path detected, checking session...')
  try {
    console.log('Calling auth()...')
    const session = await auth()
    
    // More thorough session validation
    const isValidSession = session && 
      session.user?.id && 
      session.user?.email && 
      session.session_token;

    if (!isValidSession) {
      console.log('❌ Session validation failed:', {
        hasSession: !!session,
        hasUserId: !!session?.user?.id,
        hasEmail: !!session?.user?.email,
        hasToken: !!session?.session_token
      })
      const signInUrl = new URL('/auth/signin', request.url)
      signInUrl.searchParams.set('return_to', pathname)
      return NextResponse.redirect(signInUrl)
    }

    // If user has organization_id and tries to access onboarding, redirect to dashboard
    if (pathname === ONBOARDING_PATH && session.user?.organization_id) {
      console.log('⚠️ User already has organization, redirecting to dashboard');
      return NextResponse.redirect(new URL('/dashboard', request.url))
    }

    // Check organization_id - but only if not already going to onboarding
    if (pathname !== ONBOARDING_PATH && !session.user?.organization_id) {
      console.log('⚠️ No organization_id found, redirecting to onboarding');
      return NextResponse.redirect(new URL(ONBOARDING_PATH, request.url))
    }

    console.log('✅ Valid session found')
    return NextResponse.next()
  } catch (error) {
    const err = error as Error
    
    console.log('🚨 Auth Error in middleware:', {
      type: typeof err,
      name: err.name,
      message: err.message,
      cause: err.cause,
      stack: err.stack
    })
    
    if (err.message?.includes('UntrustedHost')) {
      console.log('❌ UntrustedHost error detected')
      const signInUrl = new URL('/auth/signin', request.url)
      signInUrl.searchParams.set('return_to', pathname)
      return NextResponse.redirect(signInUrl)
    }
    
    const isJWTError = err.message?.includes('JWTSessionError') || 
                      err.name === 'JWTSessionError' ||
                      (err.cause as Error)?.message?.includes('no matching decryption secret')
    
    if (isJWTError) {
      console.log('❌ JWT Session Error detected')
      const signInUrl = new URL('/auth/signin', request.url)
      signInUrl.searchParams.set('return_to', pathname)
      signInUrl.searchParams.set('error', 'session_expired')
      return NextResponse.redirect(signInUrl)
    }
    
    throw error
  }
}

// Update the matcher configuration
export const config = {
  matcher: [
    // Protected paths
    '/admin/:path*',
    '/admin-dashboard/:path*',
    '/superuser/:path*',
    // Add other paths that need protection
    '/dashboard/:path*',
    '/tokens/:path*',
    '/endpoints/:path*',
    '/onboarding/:path*', // Include onboarding for auth check
    '/test-sets/:path*',
    '/models/:path*',
    '/organizations/:path*',
    '/settings/:path*',
    '/profile/:path*',
  ],
}
