'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { CircularProgress, Box, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { getClientUpstreamApiBaseUrl } from '@/utils/url-resolver';
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';
import { lightTheme } from '@/styles/theme';

export default function SignIn() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>('Hang tight...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuth = async () => {
      try {
        const errorParam = searchParams.get('error');
        const postLogout = searchParams.get('post_logout');
        const sessionExpired = searchParams.get('session_expired');
        const forceLogout = searchParams.get('force_logout');

        if (
          errorParam === 'session_expired' ||
          sessionExpired === 'true' ||
          forceLogout === 'true'
        ) {
          window.location.href = '/';
          return;
        }

        if (postLogout === 'true') {
          window.location.href = '/';
          return;
        }

        const authCode = searchParams.get('code');
        const incomingToken = searchParams.get('session_token');

        let sessionToken = incomingToken;
        let refreshToken: string | null = null;

        if (authCode && !sessionToken) {
          setStatus('Exchanging auth code...');

          const exchangeResponse = await fetch(
            `${getClientUpstreamApiBaseUrl()}/auth/exchange-code`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code: authCode }),
            }
          );

          if (!exchangeResponse.ok) {
            setError(
              'Authentication code expired or invalid. Please try again.'
            );
            return;
          }

          const exchangeData = await exchangeResponse.json();
          sessionToken = exchangeData.session_token;
          refreshToken = exchangeData.refresh_token || null;
        }

        if (sessionToken) {
          setStatus('Verifying session...');

          const result = await signIn('credentials', {
            session_token: sessionToken,
            refresh_token: refreshToken || '',
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

        const returnTo = searchParams.get('return_to');
        setStatus('Redirecting to login...');

        const homeUrl = new URL('/', window.location.origin);
        if (returnTo) {
          homeUrl.searchParams.set('return_to', returnTo);
        }
        window.location.replace(homeUrl.toString());
      } catch (_error) {
        setError('Authentication error. Please try again.');
      }
    };

    handleAuth();
  }, [searchParams]);

  return (
    <ThemeProvider theme={lightTheme}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          gap: 2,
          bgcolor: 'background.default',
          position: 'relative',
        }}
      >
        <BackgroundDecoration />
        <Box
          sx={{
            position: 'relative',
            zIndex: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
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
      </Box>
    </ThemeProvider>
  );
}
