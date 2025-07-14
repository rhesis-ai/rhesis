'use client';

import { API_CONFIG } from './api-client/config';

export interface User {
  id: string;
  name: string;
  email: string;
  image?: string;
  organization_id?: string;
}

export interface Session {
  user: User;
}

export async function getSession(): Promise<Session | null> {
  // Get session token from cookie
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('next-auth.session-token='))
    ?.split('=')[1];

  if (!cookieValue) return null;

  // Extract the actual JWT token from the session data
  let token = cookieValue;
  try {
    const sessionData = JSON.parse(decodeURIComponent(cookieValue));
    if (sessionData && typeof sessionData === 'object' && sessionData.session_token) {
      token = sessionData.session_token;
    }
  } catch (error) {
    // If JSON parsing fails, treat as direct token
    console.log('⚠️ [DEBUG] Session cookie is not JSON, treating as direct token');
  }

  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/auth/verify?session_token=${token}`,
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    if (!data.authenticated || !data.user) {
      return null;
    }

    return {
      user: data.user
    };
  } catch (error) {
    console.error('Session error:', error);
    return null;
  }
}

export async function clearAllSessionData() {
  console.log('🟡 [DEBUG] clearAllSessionData called - starting session cleanup');
  
  // List of all cookies to clear
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

  console.log('🟡 [DEBUG] Clearing cookies:', cookiesToClear);

  // Clear cookies with both domain and non-domain options
  cookiesToClear.forEach(name => {
    // Clear without domain (for development)
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`;
    
    // Clear with domain (for production)
    if (process.env.NODE_ENV === 'production') {
      document.cookie = `${name}=; domain=rhesis.ai; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`;
    }
  });

  console.log('🟡 [DEBUG] Clearing localStorage items');
  // Clear any local storage items
  localStorage.removeItem('next-auth.message');
  localStorage.removeItem('next-auth.callback-url');
  
  console.log('🟡 [DEBUG] Adding 500ms delay before redirect');
  // Add a delay before redirecting to ensure cookies are cleared
  await new Promise(resolve => setTimeout(resolve, 500));
  
  console.log('🟡 [DEBUG] Redirecting to home page /');
  // Force reload to clear any in-memory state and redirect to home page
  window.location.href = '/';
} 