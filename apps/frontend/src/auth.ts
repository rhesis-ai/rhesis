import NextAuth, { type NextAuthConfig, type User } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWTCallbackParams, SessionCallbackParams } from './types/next-auth.d';
import {
  SESSION_DURATION_MS,
  SESSION_DURATION_SECONDS,
} from './constants/auth';
import { getServerBackendUrl } from './utils/url-resolver';

if (!process.env.NEXTAUTH_SECRET) {
  throw new Error(
    'NEXTAUTH_SECRET environment variable is not set. Please check your environment configuration.'
  );
}

const BACKEND_URL = getServerBackendUrl();

export const authConfig: NextAuthConfig = {
  trustHost: true,
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        session_token: { type: 'text' },
        refresh_token: { type: 'text' },
      },
      async authorize(credentials, _request): Promise<User | null> {
        try {
          const sessionToken = credentials?.session_token as string | undefined;
          const refreshToken = credentials?.refresh_token as string | undefined;
          if (!sessionToken) {
            return null;
          }

          const response = await fetch(`${BACKEND_URL}/auth/verify`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/json',
            },
            body: JSON.stringify({ session_token: sessionToken }),
          });

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
            is_email_verified: data.user.is_email_verified ?? true,
            session_token: sessionToken,
            refresh_token: refreshToken || undefined,
          };
        } catch (_error) {
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
    encode: async ({ secret: _secret, token }) => {
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
      } catch (_error) {
        return '';
      }
    },
    decode: async ({ secret: _secret, token }) => {
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
          } catch (_jwtError) {
            // If JWT parsing fails, fall back to JSON parsing
          }
        }

        // Try to parse as JSON
        if (token.startsWith('{')) {
          return JSON.parse(token);
        }

        return token;
      } catch (_error) {
        return null;
      }
    },
  },
  callbacks: {
    async jwt({ token, user }: JWTCallbackParams) {
      // Initial sign-in: store tokens + compute expiry
      if (user) {
        token.user = {
          ...user,
          image: user.picture || user.image || null,
        };
        token.session_token = user.session_token;
        token.refresh_token = user.refresh_token;

        // Decode the access token to read its exp claim
        if (user.session_token) {
          try {
            const [, payloadB64] = user.session_token.split('.');
            const payload = JSON.parse(
              Buffer.from(payloadB64, 'base64url').toString('utf-8')
            );
            token.access_token_expires = payload.exp as number;
          } catch {
            // Fallback: treat as 15 min from now
            token.access_token_expires =
              Math.floor(Date.now() / 1000) + 15 * 60;
          }
        }

        return token;
      }

      // Subsequent requests: check if the access token is still valid.
      // Refresh proactively 60 seconds before expiry.
      const expiresAt = (token.access_token_expires as number) ?? 0;
      const nowSeconds = Math.floor(Date.now() / 1000);

      if (nowSeconds < expiresAt - 60) {
        // Access token is still fresh
        return token;
      }

      // Access token is expired or about to expire — refresh it
      if (!token.refresh_token) {
        // No refresh token available; force re-login
        token.error = 'RefreshTokenMissing';
        return token;
      }

      try {
        const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: token.refresh_token }),
        });

        if (!res.ok) {
          token.error = 'RefreshTokenError';
          return token;
        }

        const data = await res.json();
        token.session_token = data.access_token;
        token.refresh_token = data.refresh_token;

        // Read expiry from the new access token
        try {
          const [, payloadB64] = data.access_token.split('.');
          const payload = JSON.parse(
            Buffer.from(payloadB64, 'base64url').toString('utf-8')
          );
          token.access_token_expires = payload.exp as number;
        } catch {
          token.access_token_expires = Math.floor(Date.now() / 1000) + 15 * 60;
        }

        delete token.error;
        return token;
      } catch {
        token.error = 'RefreshTokenError';
        return token;
      }
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
        // Expose the current (possibly refreshed) access token
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
    async signOut() {},
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
        secure: process.env.FRONTEND_ENV !== 'development',
        maxAge: SESSION_DURATION_SECONDS,
        // Use undefined domain to isolate sessions per subdomain (prevents cross-environment conflicts)
        domain: undefined,
      },
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
