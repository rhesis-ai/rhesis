'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
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

          // Set cookie with proper domain - handle different environments
          const hostname = window.location.hostname;
          const isLocalhost =
            hostname === 'localhost' || hostname === '127.0.0.1';

          let cookieOptions;
          if (isLocalhost) {
            cookieOptions = 'path=/; samesite=lax';
          } else {
            // For deployed environments, use no domain (defaults to current hostname for isolation)
            cookieOptions = `path=/; secure; samesite=lax`;
          }

          document.cookie = `next-auth.session-token=${incomingToken}; ${cookieOptions}`;

          // Verify the cookie was set
          setTimeout(() => {
            const cookies = document.cookie.split(';').map(c => c.trim());
            const _sessionCookie = cookies.find(c =>
              c.startsWith('next-auth.session-token=')
            );
          }, 50);

          setStatus('Authentication successful, redirecting...');
          const returnTo = searchParams.get('return_to') || '/dashboard';

          // Small delay to ensure cookie is set
          setTimeout(() => {
            window.location.href = returnTo;
          }, 100);
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
