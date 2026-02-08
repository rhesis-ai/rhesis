'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { CircularProgress, Box, Typography } from '@mui/material';

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

        const incomingToken = searchParams.get('session_token');

        if (incomingToken) {
          setStatus('Verifying session token...');

          // Use NextAuth to properly set the httpOnly session cookie server-side.
          // This ensures the cookie is secure and cannot be read by JavaScript (XSS protection).
          const result = await signIn('credentials', {
            session_token: incomingToken,
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
        setError(`Authentication error: ${err.message}`);
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
