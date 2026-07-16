import NextAuth, { type NextAuthConfig, type User } from 'next-auth';
import type { NextResponse } from 'next/server';
import CredentialsProvider from 'next-auth/providers/credentials';
import {
  decode as defaultDecode,
  encode as defaultEncode,
  getToken,
} from 'next-auth/jwt';
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
// name when no explicit `salt` is passed to `getToken()`/`encode()`).
const SESSION_COOKIE_NAME = 'next-auth.session-token';

// Shared with `authConfig.cookies.sessionToken.options` below — also used by
// `applyRefreshedSessionCookie()` to re-set the cookie outside NextAuth's own
// request cycle (see `getFreshAccessToken()`), so a manually-issued cookie is
// never out of sync with the one NextAuth itself would have written.
const SESSION_COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  path: '/',
  secure: shouldUseSecureCookies(),
  maxAge: SESSION_DURATION_SECONDS,
  // Use undefined domain to isolate sessions per subdomain (prevents
  // cross-environment conflicts).
  domain: undefined,
};

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

// `getFreshAccessToken()` deliberately never rewrites the session cookie (see
// its own docstring), and only a full page navigation (which runs the `jwt`
// callback) persists a refreshed cookie. So once a client-side-only session
// runs past the cookie's frozen `access_token_expires`, EVERY subsequent
// request — not just a narrow window near one token's expiry, but for the
// rest of the session until the next hard navigation — reads that same
// stale cookie and independently decides it needs a refresh.
// `activeRefreshes` only coalesces requests that overlap while in flight; it
// does nothing for requests arriving a few hundred ms apart, each after the
// previous refresh already completed — a real thundering herd that map fails
// to prevent. This short-lived cache closes that gap: a refresh result stays
// reusable for REFRESH_RESULT_TTL_MS after it resolves, so a burst of
// near-sequential requests (e.g. a page firing several API calls at once)
// shares one backend round trip instead of one each. It does NOT fix the
// underlying cause above — that needs the cookie itself kept current.
//
// Safe to key by the input refresh token: this function is only ever called
// with the browser's stable, non-rotating UI refresh token (see
// `verify_and_refresh_token`'s client_id-IS-NULL path) — rotating
// client-bound tokens never flow through NextAuth's server code, so caching
// by the pre-call token can't collide with reuse-detection semantics.
const REFRESH_RESULT_TTL_MS = 5_000;
const recentRefreshes = new Map<
  string,
  { result: RefreshResult; cachedAt: number }
>();

async function refreshAccessToken(
  refreshToken: string
): Promise<RefreshResult> {
  const cached = recentRefreshes.get(refreshToken);
  if (cached && Date.now() - cached.cachedAt < REFRESH_RESULT_TTL_MS) {
    return cached.result;
  }

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
    const result = await promise;
    recentRefreshes.set(refreshToken, { result, cachedAt: Date.now() });
    // Self-evicting: guarantees the entry is cleaned up even if this exact
    // token is never looked up again, so the map can't grow unbounded across
    // a long-running process. The reference check guards against evicting a
    // newer entry in the unlikely event this token gets refreshed again
    // before the timeout fires.
    setTimeout(() => {
      if (recentRefreshes.get(refreshToken)?.result === result) {
        recentRefreshes.delete(refreshToken);
      }
    }, REFRESH_RESULT_TTL_MS);
    return result;
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
export function decodeJwtUser(jwt: string): SessionUserClaims | null {
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

export interface FreshAccessToken {
  accessToken: string | null;
  /**
   * A newly-encoded session cookie value, present only when this call
   * actually performed a refresh. `null` when the existing token was
   * already fresh, or when refreshing failed. See `applyRefreshedSessionCookie`.
   */
  refreshedCookie: string | null;
}

/**
 * Server-only helper that returns a fresh backend access token without ever
 * exposing it to the browser. Used by the `/api/backend/*` proxy (to inject
 * `Authorization` on behalf of the client) and by `createServerApiFactory`
 * (Server Components / actions calling the backend directly).
 *
 * Reads the token via a raw `getToken()` call rather than through NextAuth's
 * own request cycle, so — unlike the `jwt` callback — nothing here
 * automatically persists a refreshed cookie back to the browser. Historically
 * this meant every request after a client-side-only session ran past its
 * cookie's frozen `access_token_expires` would independently decide it
 * needed a refresh, forever, until the next full page navigation (the only
 * other path that runs the `jwt` callback and rewrites the cookie). This
 * function now re-encodes and returns an updated cookie value whenever it
 * actually performs a refresh, so a caller that CAN set cookies (the BFF
 * proxy route) can persist it — closing that gap. Callers that can't set
 * cookies (Server Component renders, via `createServerApiFactory`) simply
 * ignore `refreshedCookie`; the next proxy call (or navigation) will catch
 * it up. This is safe specifically because UI logins mint "stable"
 * (non-rotating) refresh tokens (see `verify_and_refresh_token` on the
 * backend) — presenting the same refresh token again next time, before this
 * cookie update is ever observed, is not treated as reuse.
 */
export async function getFreshAccessToken(req: {
  headers: Headers | Record<string, string>;
}): Promise<FreshAccessToken> {
  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
    cookieName: SESSION_COOKIE_NAME,
  });

  const sessionToken = token?.session_token as string | undefined;
  if (!token || !sessionToken) {
    return { accessToken: null, refreshedCookie: null };
  }

  const refreshed = await resolveFreshToken({
    session_token: sessionToken,
    refresh_token: token.refresh_token as string | undefined,
    access_token_expires: token.access_token_expires as number | undefined,
  });

  if (refreshed.error) {
    return { accessToken: null, refreshedCookie: null };
  }

  let refreshedCookie: string | null = null;
  if (refreshed.session_token !== sessionToken) {
    // An actual refresh happened (as opposed to the token already being
    // fresh) — re-encode the full original claims with only the
    // token/expiry fields swapped, so nothing else carried on the token
    // (`user`, `sub`, etc.) is lost.
    refreshedCookie = await defaultEncode({
      token: {
        ...token,
        session_token: refreshed.session_token,
        refresh_token: refreshed.refresh_token,
        access_token_expires: refreshed.access_token_expires,
      },
      secret: process.env.NEXTAUTH_SECRET as string,
      salt: SESSION_COOKIE_NAME,
      maxAge: SESSION_DURATION_SECONDS,
    });
  }

  return { accessToken: refreshed.session_token ?? null, refreshedCookie };
}

// Auth.js starts chunking session cookies (`name.0`, `name.1`, …) at
// ~3933 bytes. `applyRefreshedSessionCookie` writes a single unchunked
// cookie; if the encoded JWE ever crossed that threshold while NextAuth had
// previously written chunks, the unchunked value and the stale chunks would
// coexist and Auth.js's SessionStore would concatenate them into garbage —
// silently logging the user out. Today's payload is ~2KB, so this is a
// guard, not an expected path.
const MAX_UNCHUNKED_COOKIE_BYTES = 3900;

/**
 * Sets the session cookie on `response` when `getFreshAccessToken()`
 * performed a refresh. No-op otherwise. Call this on every response from a
 * route handler that used `getFreshAccessToken()`, right before returning it.
 */
export function applyRefreshedSessionCookie(
  response: NextResponse,
  refreshedCookie: string | null
): void {
  if (!refreshedCookie) return;
  if (refreshedCookie.length > MAX_UNCHUNKED_COOKIE_BYTES) {
    // Skipping is safe: the refresh itself already succeeded for THIS
    // request; the cookie just stays stale, so the next request refreshes
    // again (the pre-persistence behavior, bounded by the refresh cache).
    console.warn(
      `[auth] refreshed session cookie is ${refreshedCookie.length} bytes ` +
        `(> ${MAX_UNCHUNKED_COOKIE_BYTES}); skipping Set-Cookie to avoid ` +
        'clashing with Auth.js cookie chunking'
    );
    return;
  }
  response.cookies.set(
    SESSION_COOKIE_NAME,
    refreshedCookie,
    SESSION_COOKIE_OPTIONS
  );
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

      // Same-origin check, NOT a string-prefix check: `startsWith(baseUrl)`
      // would accept `https://app.example.com.evil.com` for a baseUrl of
      // `https://app.example.com` — a classic open redirect. Resolving
      // relative to baseUrl also keeps plain-path callbackUrls ("/foo")
      // working.
      try {
        const target = new URL(url, baseUrl);
        return target.origin === new URL(baseUrl).origin
          ? target.toString()
          : baseUrl;
      } catch {
        return baseUrl;
      }
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
      name: SESSION_COOKIE_NAME,
      options: SESSION_COOKIE_OPTIONS,
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
