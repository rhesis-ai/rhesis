import { Session as NextAuthSession, User as NextAuthUser } from 'next-auth';
import { JWT as NextAuthJWT } from 'next-auth/jwt';

/**
 * Profile fields safe to expose to the client (via session.user / token.user).
 * Deliberately excludes session_token/refresh_token — those must reach the
 * client only via the top-level session.session_token (access token; short-
 * lived, meant for the browser) and never at all for refresh_token. Build
 * SessionUser objects field-by-field; never spread a `User` (below) into one,
 * or the tokens ride along and leak through GET /api/auth/session.
 */
export interface SessionUser {
  id?: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  picture?: string | null;
  organization_id?: string;
  is_email_verified?: boolean;
}

declare module 'next-auth' {
  interface Session {
    session_token?: string;
    user?: SessionUser;
    expires: string;
    error?: string;
  }

  /** Wire shape returned by authorize() — the only place session_token/
   * refresh_token should exist on a "user"-shaped object. Consumed once by
   * the jwt callback's initial-login branch, which copies profile fields
   * into a SessionUser and stores the tokens separately on the token. */
  interface User extends NextAuthUser {
    id?: string;
    name?: string | null;
    email?: string | null;
    image?: string | null;
    picture?: string | null;
    organization_id?: string;
    session_token?: string;
    refresh_token?: string;
    is_email_verified?: boolean;
  }
}

declare module 'next-auth/jwt' {
  interface JWT extends NextAuthJWT {
    session_token?: string;
    refresh_token?: string;
    /** Unix timestamp (seconds) when the access token expires */
    access_token_expires?: number;
    user?: SessionUser;
    /** Set when a refresh attempt fails; forces re-login */
    error?: string;
  }
}

export interface JWTCallbackParams {
  token: NextAuthJWT;
  user?: User | null;
  session?: NextAuthSession | null;
  trigger?: 'signIn' | 'signUp' | 'update';
}

export interface SessionCallbackParams {
  session: Session;
  token: NextAuthJWT;
  trigger?: 'update';
  newSession?: Session | null;
}
