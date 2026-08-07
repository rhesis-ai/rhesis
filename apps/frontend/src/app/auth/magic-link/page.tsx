'use client';

import { useEffect, useState } from 'react';
import { Typography, CircularProgress, Alert, Button } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { useAuthStyles } from '@/components/auth/useAuthStyles';

export default function MagicLinkPage() {
  const { heading, primaryButton } = useAuthStyles();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'error'>('loading');
  const [message, setMessage] = useState('Signing you in...');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid or missing magic link token.');
      return;
    }

    const verify = async () => {
      try {
        const response = await fetch(
          `${getClientApiBaseUrl()}/auth/magic-link/verify`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Magic link verification failed');
        }

        if (data.auth_code) {
          const result = await signIn('credentials', {
            code: data.auth_code,
            redirect: false,
          });

          if (result?.error) {
            throw new Error(result.error);
          }

          const redirectTo = data.user?.organization_id
            ? '/architect'
            : '/onboarding';
          window.location.href = redirectTo;
          return;
        }

        throw new Error('No auth code received');
      } catch (err) {
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'Sign-in failed');
      }
    };

    verify();
  }, [token]);

  return (
    <AuthPageShell>
      {status === 'loading' && (
        <>
          <CircularProgress />
          <Typography variant="body1">{message}</Typography>
        </>
      )}

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: 48, color: 'error.main' }} />
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Sign-in failed
          </Typography>
          <Alert severity="error" sx={{ width: '100%' }}>
            {message}
          </Alert>
          <Typography variant="body2" color="text.secondary" align="center">
            The magic link may have expired. Please request a new one.
          </Typography>
          <Button
            variant="contained"
            href="/"
            fullWidth
            sx={{ ...primaryButton, mt: 1 }}
          >
            Back to sign in
          </Button>
        </>
      )}
    </AuthPageShell>
  );
}
