import { Session as NextAuthSession, User as NextAuthUser } from 'next-auth';
import { JWT as NextAuthJWT } from 'next-auth/jwt';

declare module 'next-auth' {
  interface Session {
    session_token?: string;
    user?: User;
    expires: string;
  }

  interface User extends NextAuthUser {
    id?: string;
    name?: string | null;
    email?: string | null;
    image?: string | null;
    picture?: string | null;
    organization_id?: string;
    session_token?: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT extends NextAuthJWT {
    session_token?: string;
    user?: User;
  }
}

export interface JWTCallbackParams {
  token: NextAuthJWT;
  user?: User | null;
  session?: NextAuthSession | null;
  trigger?: "signIn" | "signUp" | "update";
}

export interface SessionCallbackParams {
  session: Session;
  token: NextAuthJWT;
  trigger?: "update";
  newSession?: any;
}