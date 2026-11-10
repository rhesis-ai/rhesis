'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { CircularProgress, Box, Typography } from '@mui/material';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { RETURN_TO_PARAM, safeReturnTo } from '@/utils/return-to';

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

        if (authCode) {
          setStatus('Verifying session...');

          // Hand the code to NextAuth; authorize() exchanges it
          // server-side so the refresh token never reaches the browser.
          const result = await signIn('credentials', {
            code: authCode,
            redirect: false,
          });

          if (result?.error) {
            setError('Authentication failed. Please try again.');
            return;
          }

          setStatus('Authentication successful, redirecting...');
          window.location.href = safeReturnTo(
            searchParams.get(RETURN_TO_PARAM)
          );
          return;
        }

        const returnTo = searchParams.get(RETURN_TO_PARAM);
        setStatus('Redirecting to login...');

        const homeUrl = new URL('/', window.location.origin);
        if (returnTo) {
          homeUrl.searchParams.set(RETURN_TO_PARAM, safeReturnTo(returnTo));
        }
        window.location.replace(homeUrl.toString());
      } catch (_error) {
        setError('Authentication error. Please try again.');
      }
    };

    handleAuth();
  }, [searchParams]);

  return (
    <AuthPageShell>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
          py: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body1" align="center">
          {status}
        </Typography>
        {error ? (
          <Typography color="error" align="center">
            {error}
          </Typography>
        ) : null}
      </Box>
    </AuthPageShell>
  );
}
