import NextAuth, {
  type NextAuthConfig,
  type User,
  type Session,
} from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWTCallbackParams, SessionCallbackParams } from './types/next-auth.d';
import type { JWT } from 'next-auth/jwt';
import type { AdapterSession } from 'next-auth/adapters';
import {
  SESSION_DURATION_MS,
  SESSION_DURATION_SECONDS,
} from './constants/auth';
import { getClientApiBaseUrl } from './utils/url-resolver';

if (!process.env.NEXTAUTH_SECRET) {
  throw new Error(
    'NEXTAUTH_SECRET environment variable is not set. Please check your environment configuration.'
  );
}

const BACKEND_URL = getClientApiBaseUrl();

export const authConfig: NextAuthConfig = {
  trustHost: true,
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        session_token: { type: 'text' },
      },
      async authorize(credentials, request): Promise<User | null> {
        try {
          const sessionToken = credentials?.session_token as string | undefined;
          if (!sessionToken) {
            return null;
          }

          const response = await fetch(
            `${BACKEND_URL}/auth/verify?session_token=${sessionToken}`,
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

          let imageUrl = data.user.picture || data.user.image;
          if (imageUrl && imageUrl.includes('googleusercontent.com')) {
            imageUrl = imageUrl.replace(/=s\d+-c$/, '=s96-c');
            if (!imageUrl.endsWith('-c')) {
              imageUrl += '=s96-c';
            }
          }

          return {
            id: data.user.id,
            name: data.user.name,
            email: data.user.email,
            image: imageUrl || null,
            picture: imageUrl || null,
            organization_id: data.user.organization_id,
            session_token: sessionToken,
          };
        } catch (error) {
          console.error('Auth error:', error);
          return null;
        }
      },
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    strategy: 'jwt',
    maxAge: SESSION_DURATION_SECONDS,
  },
  jwt: {
    encode: async ({ secret, token }) => {
      if (!token) return '';
      try {
        // If token has a session_token field, use it directly (it's already a JWT)
        if (token.session_token && typeof token.session_token === 'string') {
          return token.session_token;
        }

        // Otherwise, encode as JSON for backward compatibility
        if (typeof token === 'string') {
          return token;
        }
        const stringified = JSON.stringify(token);
        return stringified;
      } catch (error) {
        console.error('JWT encode error:', error);
        return '';
      }
    },
    decode: async ({ secret, token }) => {
      if (!token) return null;
      try {
        if (typeof token !== 'string') {
          return token;
        }

        // If it's a JWT token (contains dots), decode it
        if (token.includes('.') && token.split('.').length === 3) {
          const [, payloadBase64] = token.split('.');
          try {
            const payload = Buffer.from(payloadBase64, 'base64url').toString(
              'utf-8'
            );
            const decoded = JSON.parse(payload);

            return {
              ...decoded,
              session_token: token,
            };
          } catch (jwtError) {
            console.error('JWT parsing error:', jwtError);
            // If JWT parsing fails, fall back to JSON parsing
          }
        }

        // Try to parse as JSON
        if (token.startsWith('{')) {
          return JSON.parse(token);
        }

        return token;
      } catch (error) {
        console.error('JWT decode error:', error);
        console.error('Failed token:', token);
        return null;
      }
    },
  },
  callbacks: {
    async jwt({ token, user }: JWTCallbackParams) {
      if (user) {
        token.user = {
          ...user,
          image: user.picture || user.image || null,
        };
        token.session_token = user.session_token;
      }
      return token;
    },
    async session({ session, token }: SessionCallbackParams) {
      const updatedSession = {
        ...session,
        expires: new Date(Date.now() + SESSION_DURATION_MS).toISOString(),
      };

      if (token.user) {
        updatedSession.user = {
          ...token.user,
          image: token.user.picture || token.user.image || null,
        };
        updatedSession.session_token = token.session_token;
      }

      return updatedSession;
    },
    async redirect({ url, baseUrl }) {
      if (url.includes('/api/auth/signout')) {
        // Redirect directly to home page after signout
        return `${baseUrl}/`;
      }

      return url.startsWith(baseUrl) ? url : baseUrl;
    },
  },
  events: {
    async signOut() {
      console.log('[AUTH] NextAuth signOut event triggered - session fully cleared');
    },
  },
  pages: {
    signIn: '/',
  },
  debug: process.env.FRONTEND_ENV === 'development',
  basePath: '/api/auth',
  cookies: {
    sessionToken: {
      name: `next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.FRONTEND_ENV === 'production',
        maxAge: SESSION_DURATION_SECONDS,
        domain:
          process.env.FRONTEND_ENV === 'production' ? '.rhesis.ai' : undefined,
      },
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
