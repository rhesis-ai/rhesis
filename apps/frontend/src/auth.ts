import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWTCallbackParams, SessionCallbackParams } from './types/next-auth.d';
import type { NextAuthConfig } from 'next-auth';
import type { User } from 'next-auth';
import type { Session } from 'next-auth';
import type { JWT } from 'next-auth/jwt';
import type { AdapterSession } from 'next-auth/adapters';

if (!process.env.NEXTAUTH_SECRET) {
  throw new Error('NEXTAUTH_SECRET environment variable is not set. Please check your environment configuration.');
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export const authConfig: NextAuthConfig = {
  trustHost: true,
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        session_token: { type: "text" }
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
            session_token: sessionToken
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
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },
  jwt: {
    encode: async ({ secret, token }) => {
      if (!token) return "";
      try {
        // console.log('Encoding token input:', {
        //   type: typeof token,
        //   isString: typeof token === 'string',
        //   value: token
        // });

        // Return the token as is if it's already a string
        if (typeof token === 'string') {
          //console.log('Returning string token as is');
          return token;
        }
        // Otherwise, stringify it
        const stringified = JSON.stringify(token);
        //console.log('Stringified token:', stringified);
        return stringified;
      } catch (error) {
        console.error('JWT encode error:', error);
        return "";
      }
    },
    decode: async ({ secret, token }) => {
      if (!token) return null;
      try {
        // console.log('Decoding token input:', {
        //   type: typeof token,
        //   isString: typeof token === 'string',
        //   value: token
        // });

        // If it's not a string, return as is
        if (typeof token !== 'string') {
          //console.log('Returning non-string token as is');
          return token;
        }

        // If it's a JSON string
        if (token.startsWith('{')) {
          //console.log('Parsing JSON string token');
          return JSON.parse(token);
        }

        // If it's a JWT token (contains two dots)
        if (token.includes('.')) {
          //console.log('Detected JWT token, decoding payload');
          const [, payloadBase64] = token.split('.');
          try {
            const payload = Buffer.from(payloadBase64, 'base64url').toString('utf-8');
            const decoded = JSON.parse(payload);
            
            return {
              ...decoded,
              session_token: token
            };
          } catch (jwtError) {
            console.error('JWT parsing error:', jwtError);
            // If JWT parsing fails, try parsing as JSON
            return JSON.parse(token);
          }
        }

        console.log('Returning string token as is');
        return token;
      } catch (error) {
        console.error('JWT decode error:', error);
        console.error('Failed token:', token);
        return null;
      }
    }
  },
  callbacks: {
    async jwt({ token, user }: JWTCallbackParams) {
      if (user) {
        token.user = {
          ...user,
          image: user.picture || user.image || null
        };
        token.session_token = user.session_token;
      }
      return token;
    },
    async session({ session, token }: SessionCallbackParams) {
      const updatedSession = {
        ...session,
        expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
      };
      
      if (token.user) {
        updatedSession.user = {
          ...token.user,
          image: token.user.picture || token.user.image || null
        };
        updatedSession.session_token = token.session_token;
      }
      
      return updatedSession;
    },
    async redirect({ url, baseUrl }) {
      if (url.includes('/api/auth/signout')) {
        // Clear frontend cookies first
        if (typeof window !== 'undefined') {
          document.cookie = 'next-auth.session-token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT';
          if (process.env.NODE_ENV === 'production') {
            document.cookie = 'next-auth.session-token=; domain=rhesis.ai; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT';
          }
        }
        
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        const frontendUrl = process.env.NEXT_PUBLIC_FRONTEND_URL || baseUrl;

        // Redirect to the main landing page which contains your custom login UI
        const customLoginUrl = `${frontendUrl}/`;
        
        // Send users to your custom login page after logout
        const returnUrl = `${backendUrl}/auth/logout?redirect_url=${encodeURIComponent(customLoginUrl)}`;
        return returnUrl;
      }
      
      return url.startsWith(baseUrl) ? url : baseUrl;
    }
  },
  events: {
    async signOut() {
      // The cookie clearing is now handled in the redirect callback
      // to ensure it happens before the backend redirect
    }
  },
  pages: {
    signIn: '/auth/signin',
  },
  debug: process.env.NODE_ENV === 'development',
  basePath: "/api/auth",
  cookies: {
    sessionToken: {
      name: `next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        maxAge: 24 * 60 * 60, // 24 hours in seconds
        domain: process.env.NODE_ENV === 'production' ? 'rhesis.ai' : undefined
      }
    }
  }
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
  
  