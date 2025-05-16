import { cookies } from 'next/headers';
import { API_CONFIG } from './api-client/config';

export interface User {
  id: string;
  email: string;
  name: string;
  picture?: string;
}

export interface Session {
  user: User;
}

export async function getSession(): Promise<Session | null> {
  const token = (await cookies()).get('rhesis_session_token')?.value;
  if (!token) return null;

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