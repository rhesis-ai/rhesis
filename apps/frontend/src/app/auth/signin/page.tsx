'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { CircularProgress, Box, Typography } from '@mui/material';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function SignIn() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>('Hang tight...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuth = async () => {
      try {
        // Check for session expiration error
        const errorParam = searchParams.get('error');
        const postLogout = searchParams.get('post_logout');
        const sessionExpired = searchParams.get('session_expired');
        const forceLogout = searchParams.get('force_logout');

        if (
          errorParam === 'session_expired' ||
          sessionExpired === 'true' ||
          forceLogout === 'true'
        ) {
          // Redirect to home page for expired sessions
          window.location.href = '/';
          return;
        }

        if (postLogout === 'true') {
          // Redirect to home page after logout
          window.location.href = '/';
          return;
        }

        // OAuth callback: exchange short-lived auth code for session token
        const authCode = searchParams.get('code');
        // Backward compatibility: also accept direct session_token (email/password flows)
        const incomingToken = searchParams.get('session_token');

        let sessionToken = incomingToken;

        if (authCode && !sessionToken) {
          setStatus('Exchanging auth code...');

          const exchangeResponse = await fetch(
            `${getClientApiBaseUrl()}/auth/exchange-code`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code: authCode }),
            }
          );

          if (!exchangeResponse.ok) {
            setError('Authentication code expired or invalid. Please try again.');
            return;
          }

          const exchangeData = await exchangeResponse.json();
          sessionToken = exchangeData.session_token;
        }

        if (sessionToken) {
          setStatus('Verifying session...');

          // Use NextAuth to properly set the httpOnly session cookie server-side.
          // This ensures the cookie is secure and cannot be read by JavaScript (XSS protection).
          const result = await signIn('credentials', {
            session_token: sessionToken,
            redirect: false,
          });

          if (result?.error) {
            setError('Authentication failed. Please try again.');
            return;
          }

          setStatus('Authentication successful, redirecting...');
          const returnTo = searchParams.get('return_to') || '/dashboard';
          window.location.href = returnTo;
          return;
        }

        // If no token and no special parameters, redirect to home page for unified login experience
        const returnTo = searchParams.get('return_to');
        setStatus('Redirecting to login...');

        // Redirect to home page which has the unified login experience
        const homeUrl = new URL('/', window.location.origin);
        if (returnTo) {
          homeUrl.searchParams.set('return_to', returnTo);
        }
        window.location.replace(homeUrl.toString());
      } catch (error) {
        const err = error as Error;
        setError('Authentication error. Please try again.');
      }
    };

    handleAuth();
  }, [searchParams]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2,
        bgcolor: 'background.default',
      }}
    >
      <CircularProgress />
      <Typography variant="body1" align="center">
        {status}
      </Typography>
      {error && (
        <Typography color="error" align="center">
          {error}
        </Typography>
      )}
    </Box>
  );
}
