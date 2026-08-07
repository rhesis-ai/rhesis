'use client';

import { useEffect, useState } from 'react';
import { Typography, CircularProgress, Alert, Button } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { DEFAULT_AUTHENTICATED_PATH } from '@/constants/paths';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { useAuthStyles } from '@/components/auth/useAuthStyles';

export default function VerifyEmailPage() {
  const { heading, primaryButton } = useAuthStyles();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    'loading'
  );
  const [message, setMessage] = useState('Verifying your email...');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid or missing verification token.');
      return;
    }

    const verify = async () => {
      try {
        const response = await fetch(
          `${getClientApiBaseUrl()}/auth/verify-email`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Verification failed');
        }

        if (data.auth_code) {
          await signIn('credentials', {
            code: data.auth_code,
            redirect: false,
          });
        }

        setStatus('success');
        setMessage(data.message || 'Email verified successfully!');
      } catch (err) {
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'Verification failed');
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

      {status === 'success' && (
        <>
          <CheckCircleIcon sx={{ fontSize: 48, color: 'success.main' }} />
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Email verified!
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            {message}
          </Typography>
          <Button
            variant="contained"
            href={DEFAULT_AUTHENTICATED_PATH}
            fullWidth
            sx={{ ...primaryButton, mt: 1 }}
          >
            Go back to app
          </Button>
        </>
      )}

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: 48, color: 'error.main' }} />
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Verification failed
          </Typography>
          <Alert severity="error" sx={{ width: '100%' }}>
            {message}
          </Alert>
          <Button variant="text" href="/" sx={{ mt: 1 }}>
            Back to sign in
          </Button>
        </>
      )}
    </AuthPageShell>
  );
}
