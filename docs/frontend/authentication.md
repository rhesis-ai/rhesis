# Authentication

This document explains the authentication system used in the Rhesis frontend application.

## Authentication Architecture

The Rhesis frontend integrates with the Rhesis backend for authentication, which in turn uses Auth0 as the identity provider. This architecture provides:

- Secure authentication via Auth0
- JWT token management
- Session handling
- Route protection
- Role-based access control

## Authentication Flow

1. **User Login**: User is redirected to Auth0 login page (or uses social login)
2. **Auth0 Authentication**: Auth0 authenticates the user and redirects back to the application
3. **Token Exchange**: The Rhesis backend exchanges the Auth0 code for access and refresh tokens
4. **Session Creation**: The backend creates a session and provides tokens to the frontend
5. **Route Protection**: Protected routes check for valid tokens
6. **Token Refresh**: Tokens are automatically refreshed when needed
7. **Logout**: User session is destroyed on logout

## Authentication Setup

The authentication is configured in `src/auth.ts`:

```tsx
import { jwtDecode } from 'jwt-decode';

// Token storage keys
const ACCESS_TOKEN_KEY = 'rhesis_access_token';
const REFRESH_TOKEN_KEY = 'rhesis_refresh_token';
const USER_KEY = 'rhesis_user';

// Auth API endpoints
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
const AUTH_ENDPOINTS = {
  login: `${API_BASE_URL}/auth/login`,
  logout: `${API_BASE_URL}/auth/logout`,
  refresh: `${API_BASE_URL}/auth/refresh`,
  user: `${API_BASE_URL}/auth/user`,
};

export interface User {
  id: string;
  email: string;
  name: string;
  picture?: string;
  roles: string[];
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

// Check if token is expired
export function isTokenExpired(token: string): boolean {
  try {
    const decoded = jwtDecode<{ exp: number }>(token);
    const currentTime = Date.now() / 1000;
    return decoded.exp < currentTime;
  } catch {
    return true;
  }
}

// Get stored tokens
export function getTokens(): AuthTokens | null {
  if (typeof window === 'undefined') return null;
  
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  
  if (!accessToken || !refreshToken) return null;
  
  const decoded = jwtDecode<{ exp: number }>(accessToken);
  const expiresIn = decoded.exp * 1000 - Date.now();
  
  return { accessToken, refreshToken, expiresIn };
}

// Store tokens
export function storeTokens(tokens: AuthTokens): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

// Clear tokens
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// Get current user
export function getUser(): User | null {
  if (typeof window === 'undefined') return null;
  
  const userJson = localStorage.getItem(USER_KEY);
  if (!userJson) return null;
  
  try {
    return JSON.parse(userJson);
  } catch {
    return null;
  }
}

// Store user
export function storeUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// Login redirect
export function loginWithRedirect(): void {
  // Store current location for redirect after login
  localStorage.setItem('auth_redirect', window.location.pathname);
  
  // Redirect to backend login endpoint which will redirect to Auth0
  window.location.href = AUTH_ENDPOINTS.login;
}

// Logout
export async function logout(): Promise<void> {
  try {
    const tokens = getTokens();
    if (tokens) {
      // Call backend logout endpoint
      await fetch(AUTH_ENDPOINTS.logout, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokens.accessToken}`,
        },
      });
    }
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    // Clear local storage
    clearTokens();
    // Redirect to home
    window.location.href = '/';
  }
}

// Refresh token
export async function refreshTokens(): Promise<AuthTokens | null> {
  const tokens = getTokens();
  if (!tokens || !tokens.refreshToken) return null;
  
  try {
    const response = await fetch(AUTH_ENDPOINTS.refresh, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refreshToken: tokens.refreshToken }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }
    
    const newTokens = await response.json();
    storeTokens(newTokens);
    return newTokens;
  } catch (error) {
    console.error('Token refresh error:', error);
    clearTokens();
    return null;
  }
}

// Get current user from API
export async function fetchUser(): Promise<User | null> {
  let tokens = getTokens();
  
  // If no tokens or access token is expired, try to refresh
  if (!tokens || isTokenExpired(tokens.accessToken)) {
    tokens = await refreshTokens();
    if (!tokens) return null;
  }
  
  try {
    const response = await fetch(AUTH_ENDPOINTS.user, {
      headers: {
        'Authorization': `Bearer ${tokens.accessToken}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }
    
    const user = await response.json();
    storeUser(user);
    return user;
  } catch (error) {
    console.error('Fetch user error:', error);
    return null;
  }
}
```

## Route Protection

Routes are protected using a custom middleware in `src/middleware.ts`:

```tsx
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isTokenExpired } from './auth';

// Routes that require authentication
const protectedRoutes = [
  '/dashboard',
  '/projects',
  '/tests',
  '/admin',
];

// Routes that are public
const publicRoutes = [
  '/',
  '/auth/callback',
  '/login',
  '/register',
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Check if the route is public
  if (publicRoutes.some(route => pathname.startsWith(route))) {
    return NextResponse.next();
  }
  
  // Check if the route is protected
  if (protectedRoutes.some(route => pathname.startsWith(route))) {
    // Get the token from cookies
    const accessToken = request.cookies.get('rhesis_access_token')?.value;
    
    // If no token or token is expired, redirect to login
    if (!accessToken || isTokenExpired(accessToken)) {
      const url = new URL('/login', request.url);
      url.searchParams.set('redirect', pathname);
      return NextResponse.redirect(url);
    }
    
    // For admin routes, check if user has admin role
    if (pathname.startsWith('/admin')) {
      // Get user roles from token or another cookie
      const userRoles = request.cookies.get('rhesis_user_roles')?.value;
      const roles = userRoles ? JSON.parse(userRoles) : [];
      
      if (!roles.includes('admin')) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
      }
    }
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/auth).*)'],
};
```

## Authentication Context

A React context is used to manage authentication state on the client:

```tsx
// src/components/providers/AuthProvider.tsx
'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { User, getUser, fetchUser, loginWithRedirect, logout, getTokens, refreshTokens } from '@/auth';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  const refreshAuth = async () => {
    const tokens = getTokens();
    if (!tokens) {
      setUser(null);
      return;
    }
    
    const currentUser = await fetchUser();
    setUser(currentUser);
  };
  
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      
      // First try to get user from local storage
      const storedUser = getUser();
      if (storedUser) {
        setUser(storedUser);
      }
      
      // Then try to fetch fresh user data
      await refreshAuth();
      
      setIsLoading(false);
    };
    
    initAuth();
    
    // Set up token refresh interval
    const tokens = getTokens();
    if (tokens) {
      const refreshTime = Math.max(tokens.expiresIn - 5 * 60 * 1000, 0); // 5 minutes before expiry
      const refreshInterval = setInterval(() => {
        refreshTokens().then(newTokens => {
          if (!newTokens) {
            clearInterval(refreshInterval);
          }
        });
      }, refreshTime);
      
      return () => clearInterval(refreshInterval);
    }
  }, []);
  
  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login: loginWithRedirect,
        logout,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
```

## Auth0 Callback Handling

The callback from Auth0 is handled by a dedicated page:

```tsx
// app/auth/callback/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { storeTokens, storeUser } from '@/auth';

export default function AuthCallback() {
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();
  
  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');
      
      if (error) {
        setError(error);
        return;
      }
      
      if (!code || !state) {
        setError('Invalid callback parameters');
        return;
      }
      
      try {
        // Exchange code for tokens with backend
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ code, state }),
        });
        
        if (!response.ok) {
          throw new Error('Failed to exchange code for tokens');
        }
        
        const data = await response.json();
        
        // Store tokens and user data
        storeTokens({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          expiresIn: data.expires_in * 1000,
        });
        
        storeUser(data.user);
        
        // Redirect to the stored redirect URL or dashboard
        const redirectUrl = localStorage.getItem('auth_redirect') || '/dashboard';
        localStorage.removeItem('auth_redirect');
        router.push(redirectUrl);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unexpected error occurred');
      }
    };
    
    handleCallback();
  }, [router, searchParams]);
  
  if (error) {
    return (
      <div className="auth-error">
        <h2>Authentication Error</h2>
        <p>{error}</p>
        <button onClick={() => router.push('/login')}>Try Again</button>
      </div>
    );
  }
  
  return (
    <div className="auth-loading">
      <h2>Authenticating...</h2>
      <p>Please wait while we complete the authentication process.</p>
    </div>
  );
}
```

## Login Component

The login component redirects to Auth0:

```tsx
// src/components/auth/LoginButton.tsx
'use client';

import { useAuth } from '@/components/providers/AuthProvider';

export default function LoginButton() {
  const { login } = useAuth();
  
  return (
    <button 
      className="login-button" 
      onClick={login}
    >
      Log In with Auth0
    </button>
  );
}
```

## Using Authentication in Components

### Protected Component

```tsx
// src/components/common/ProtectedComponent.tsx
'use client';

import { useAuth } from '@/components/providers/AuthProvider';

export default function ProtectedComponent({ 
  children,
  fallback = <div>Please log in to access this content</div>,
}: { 
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return fallback;
  }
  
  return <>{children}</>;
}
```

### User Profile

```tsx
// src/components/auth/UserProfile.tsx
'use client';

import { useAuth } from '@/components/providers/AuthProvider';

export default function UserProfile() {
  const { user, logout } = useAuth();
  
  if (!user) {
    return null;
  }
  
  return (
    <div className="user-profile">
      {user.picture && <img src={user.picture} alt={user.name} />}
      <div className="user-info">
        <h3>{user.name}</h3>
        <p>{user.email}</p>
      </div>
      <button onClick={logout}>Log Out</button>
    </div>
  );
}
```

## Role-Based Access Control

Role-based access control is implemented using the user's roles:

```tsx
// src/components/common/RoleBasedAccess.tsx
'use client';

import { useAuth } from '@/components/providers/AuthProvider';

interface RoleBasedAccessProps {
  children: React.ReactNode;
  requiredRoles: string[];
  fallback?: React.ReactNode;
}

export default function RoleBasedAccess({ 
  children, 
  requiredRoles,
  fallback = <div>You don't have permission to access this content</div>,
}: RoleBasedAccessProps) {
  const { user } = useAuth();
  
  if (!user) {
    return null;
  }
  
  const hasRequiredRole = requiredRoles.some(role => user.roles.includes(role));
  
  if (!hasRequiredRole) {
    return fallback;
  }
  
  return <>{children}</>;
}
```

## Auth Provider Setup

The auth provider is set up in the root layout:

```tsx
// app/layout.tsx
import { AuthProvider } from '@/components/providers/AuthProvider';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

## Security Considerations

1. **HTTPS**: Always use HTTPS in production
2. **Token Storage**: Store tokens securely in memory or HTTP-only cookies when possible
3. **Token Expiry**: Configure appropriate token expiry times in Auth0
4. **Refresh Tokens**: Handle token refresh securely
5. **CORS**: Ensure proper CORS configuration on the backend
6. **Error Handling**: Use generic error messages to prevent information leakage 