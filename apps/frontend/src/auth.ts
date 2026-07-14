import NextAuth, { type NextAuthConfig, type User } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWTCallbackParams, SessionCallbackParams } from './types/next-auth.d';
import {
  SESSION_DURATION_MS,
  SESSION_DURATION_SECONDS,
} from './constants/auth';
import {
  getServerBackendUrl,
  shouldUseSecureCookies,
} from './utils/url-resolver';

if (!process.env.NEXTAUTH_SECRET) {
  throw new Error(
    'NEXTAUTH_SECRET environment variable is not set. Please check your environment configuration.'
  );
}

// Make FRONTEND_URL the single source of truth for NextAuth's base URL.
// Auth.js reads AUTH_URL/NEXTAUTH_URL from process.env at runtime (see
// next-auth/lib/env.js:reqWithEnvURL); without it, trustHost infers the base
// URL from the container hostname (e.g. http://<container-id>:3000), which
// breaks post-login redirects. An explicitly set AUTH_URL/NEXTAUTH_URL wins.
if (
  !process.env.AUTH_URL &&
  !process.env.NEXTAUTH_URL &&
  process.env.FRONTEND_URL
) {
  process.env.NEXTAUTH_URL = process.env.FRONTEND_URL;
}

const BACKEND_URL = getServerBackendUrl();

interface RefreshResult {
  access_token: string;
  refresh_token: string;
}

// Concurrency guard: coalesces simultaneous refreshes for the SAME refresh
// token into one in-flight /auth/refresh call. This avoids a thundering herd
// when several server-side session checks (RSC renders, parallel tabs) cross
// the expiry boundary at once.
//
// The map MUST be keyed by refresh token, never a single shared promise: the
// NextAuth server handles many users in one Node process, so a process-global
// singleton would hand one user's freshly-minted tokens to another user
// racing a refresh at the same instant.
const activeRefreshes = new Map<string, Promise<RefreshResult>>();

async function refreshAccessToken(
  refreshToken: string
): Promise<RefreshResult> {
  const inFlight = activeRefreshes.get(refreshToken);
  if (inFlight) return inFlight;

  const promise = (async () => {
    const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      throw new Error('RefreshTokenError');
    }

    return (await res.json()) as RefreshResult;
  })();

  activeRefreshes.set(refreshToken, promise);
  try {
    return await promise;
  } finally {
    activeRefreshes.delete(refreshToken);
  }
}

function decodeJwtExpiry(jwt: string): number {
  try {
    const [, payloadB64] = jwt.split('.');
    const payload = JSON.parse(
      Buffer.from(payloadB64, 'base64url').toString('utf-8')
    );
    return payload.exp as number;
  } catch {
    return Math.floor(Date.now() / 1000) + 15 * 60;
  }
}

interface SessionUserClaims {
  id?: string;
  name?: string | null;
  email?: string | null;
  picture?: string | null;
  image?: string | null;
  organization_id?: string;
  is_email_verified?: boolean;
}

/** Decode the `user` claim from a backend-minted session JWT. */
function decodeJwtUser(jwt: string): SessionUserClaims | null {
  try {
    const [, payloadB64] = jwt.split('.');
    const payload = JSON.parse(
      Buffer.from(payloadB64, 'base64url').toString('utf-8')
    );
    return (payload.user as SessionUserClaims) ?? null;
  } catch {
    return null;
  }
}

export const authConfig: NextAuthConfig = {
  trustHost: true,
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        // Every login flow (email/password, OAuth, magic-link, email
        // verification, quick-start) hands NextAuth a short-lived,
        // single-use auth code — never the raw tokens. The exchange
        // happens here, server-side, so the refresh token only ever
        // lives in the httpOnly session cookie and never reaches the
        // browser.
        code: { type: 'text' },
      },
      async authorize(credentials, _request): Promise<User | null> {
        try {
          const code = credentials?.code as string | undefined;
          if (!code) {
            return null;
          }

          const response = await fetch(`${BACKEND_URL}/auth/exchange-code`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/json',
            },
            body: JSON.stringify({ code }),
          });

          if (!response.ok) {
            return null;
          }

          const { session_token, refresh_token } = await response.json();
          if (!session_token) {
            return null;
          }

          // The session token is freshly minted and signed by our own
          // backend in this same request, so decode its claims for user
          // info rather than paying for a second /auth/verify round-trip.
          const claims = decodeJwtUser(session_token);
          if (!claims) {
            return null;
          }

          let imageUrl = claims.picture || claims.image;
          if (imageUrl && imageUrl.includes('googleusercontent.com')) {
            imageUrl = imageUrl.replace(/=s\d+-c$/, '=s96-c');
            if (!imageUrl.endsWith('-c')) {
              imageUrl += '=s96-c';
            }
          }

          return {
            id: claims.id,
            name: claims.name,
            email: claims.email,
            image: imageUrl || null,
            picture: imageUrl || null,
            organization_id: claims.organization_id,
            is_email_verified: claims.is_email_verified ?? true,
            session_token,
            refresh_token: refresh_token || undefined,
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
  // No custom jwt.encode/decode: NextAuth encrypts the session cookie as a
  // JWE (its secure default). The backend access token, refresh token, and
  // expiry live inside that encrypted payload — never as a plaintext cookie
  // value. The access token is surfaced to the app only through the session
  // object (session.session_token); nothing reads the raw cookie.
  callbacks: {
    async jwt({ token, user, trigger, session }: JWTCallbackParams) {
      if (user) {
        token.user = {
          ...user,
          image: user.picture || user.image || null,
        };
        token.session_token = user.session_token;
        token.refresh_token = user.refresh_token;

        if (user.session_token) {
          token.access_token_expires = decodeJwtExpiry(user.session_token);
        }

        return token;
      }

      // Session update trigger (e.g. after onboarding attaches the user to
      // an organization, the backend returns a fresh ACCESS token). Swap in
      // the new access token but PRESERVE the existing refresh token — the
      // refresh token is unchanged by onboarding and must not be dropped, or
      // the session would lose the ability to refresh.
      if (trigger === 'update' && session?.session_token) {
        token.session_token = session.session_token;
        token.access_token_expires = decodeJwtExpiry(session.session_token);
        if (token.user) {
          // Reflect any updated org/profile claims from the new token.
          const claims = decodeJwtUser(session.session_token);
          if (claims) {
            token.user = {
              ...token.user,
              organization_id:
                claims.organization_id ?? token.user.organization_id,
              name: claims.name ?? token.user.name,
            };
          }
        }
        delete token.error;
        return token;
      }

      const expiresAt = (token.access_token_expires as number) ?? 0;
      const nowSeconds = Math.floor(Date.now() / 1000);

      if (nowSeconds < expiresAt - 60) {
        return token;
      }

      if (!token.refresh_token) {
        token.error = 'RefreshTokenMissing';
        return token;
      }

      try {
        const data = await refreshAccessToken(
          token.refresh_token as string
        );
        token.session_token = data.access_token;
        token.refresh_token = data.refresh_token;
        token.access_token_expires = decodeJwtExpiry(data.access_token);
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
        updatedSession.session_token = token.session_token;
      }

      if (token.error) {
        updatedSession.error = token.error as string;
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
        secure: shouldUseSecureCookies(),
        maxAge: SESSION_DURATION_SECONDS,
        // Use undefined domain to isolate sessions per subdomain (prevents cross-environment conflicts)
        domain: undefined,
      },
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
