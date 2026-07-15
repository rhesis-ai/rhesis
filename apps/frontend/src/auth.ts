import NextAuth, { type NextAuthConfig, type User } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { decode as defaultDecode, getToken } from 'next-auth/jwt';
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

// Keep in sync with `authConfig.cookies.sessionToken.name` below — also
// doubles as the JWE decryption `salt` (Auth.js derives it from the cookie
// name when no explicit `salt` is passed to `getToken()`).
const SESSION_COOKIE_NAME = 'next-auth.session-token';

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

interface TokenFreshness {
  session_token?: string;
  refresh_token?: string;
  access_token_expires?: number;
  error?: string;
}

/**
 * Given the token fields persisted on the session, returns them unchanged if
 * the access token is still fresh, or refreshes via the coalescing map
 * otherwise. Shared by the `jwt` callback (which persists the result back
 * onto the session cookie) and `getFreshAccessToken()` (which returns it for
 * a single server-side call, e.g. from the BFF proxy, without persisting).
 */
async function resolveFreshToken(
  state: TokenFreshness
): Promise<TokenFreshness> {
  const expiresAt = state.access_token_expires ?? 0;
  const nowSeconds = Math.floor(Date.now() / 1000);

  if (nowSeconds < expiresAt - 60) {
    return state;
  }

  if (!state.refresh_token) {
    return { ...state, error: 'RefreshTokenMissing' };
  }

  try {
    const data = await refreshAccessToken(state.refresh_token);
    return {
      session_token: data.access_token,
      refresh_token: data.refresh_token,
      access_token_expires: decodeJwtExpiry(data.access_token),
    };
  } catch {
    return { ...state, error: 'RefreshTokenError' };
  }
}

/**
 * Server-only helper that returns a fresh backend access token without ever
 * exposing it to the browser. Used by the `/api/backend/*` proxy (to inject
 * `Authorization` on behalf of the client) and by `createServerApiFactory`
 * (Server Components / actions calling the backend directly).
 *
 * Deliberately does NOT rewrite the session cookie: UI logins mint "stable"
 * (non-rotating) refresh tokens (see `verify_and_refresh_token` on the
 * backend), so calling `/auth/refresh` again on the next request with the
 * same refresh token is safe — there's no reuse-detection penalty. Normal
 * page navigation (via `auth()` in `proxy.ts`/layout) still persists a
 * refreshed cookie through the ordinary `jwt` callback path; this helper
 * just covers API calls between navigations, bounded by the same
 * `activeRefreshes` coalescing map.
 */
export async function getFreshAccessToken(req: {
  headers: Headers | Record<string, string>;
}): Promise<string | null> {
  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
    cookieName: SESSION_COOKIE_NAME,
  });

  const sessionToken = token?.session_token as string | undefined;
  if (!sessionToken) {
    return null;
  }

  const refreshed = await resolveFreshToken({
    session_token: sessionToken,
    refresh_token: token?.refresh_token as string | undefined,
    access_token_expires: token?.access_token_expires as number | undefined,
  });

  return refreshed.error ? null : (refreshed.session_token ?? null);
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
  // No custom jwt.encode: NextAuth encrypts the session cookie as a JWE
  // (its secure default). The backend access token, refresh token, and
  // expiry live inside that encrypted payload — never as a plaintext cookie
  // value. The access token is surfaced to the app only through the session
  // object (session.session_token); nothing reads the raw cookie.
  jwt: {
    // Fall back to null instead of throwing when a cookie can't be
    // decrypted as JWE. This is expected for any cookie minted before
    // this encryption was introduced (a plaintext-JSON blob under the old
    // custom encode) — treat it as "no session" rather than a hard
    // JWTSessionError that crashes rendering. Auth.js resolves a null
    // token to an unauthenticated session, so the user is simply prompted
    // to sign in again.
    async decode(params) {
      try {
        return await defaultDecode(params);
      } catch {
        return null;
      }
    },
  },
  callbacks: {
    async jwt({ token, user, trigger, session }: JWTCallbackParams) {
      if (user) {
        // Build token.user explicitly (never spread the raw `user` object) —
        // it carries session_token/refresh_token from authorize(), and
        // token.user is exactly what the session callback forwards to the
        // client via session.user. Spreading it here previously leaked the
        // refresh token to browser JS through GET /api/auth/session.
        token.user = {
          id: user.id,
          name: user.name,
          email: user.email,
          image: user.picture || user.image || null,
          picture: user.picture,
          organization_id: user.organization_id,
          is_email_verified: user.is_email_verified,
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

      const refreshed = await resolveFreshToken({
        session_token: token.session_token as string | undefined,
        refresh_token: token.refresh_token as string | undefined,
        access_token_expires: token.access_token_expires as
          | number
          | undefined,
      });
      token.session_token = refreshed.session_token;
      token.refresh_token = refreshed.refresh_token;
      token.access_token_expires = refreshed.access_token_expires;
      if (refreshed.error) {
        token.error = refreshed.error;
      } else {
        delete token.error;
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
        // Deliberately NOT exposing token.session_token here. The access
        // token must never reach browser JS — client API calls go through
        // the same-origin `/api/backend` proxy (see getBaseUrl()), which
        // injects it server-side via getFreshAccessToken(). Server
        // components/actions use getFreshAccessToken() directly, never
        // session.session_token.
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
