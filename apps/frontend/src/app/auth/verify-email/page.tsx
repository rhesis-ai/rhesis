'use client';

import { useEffect, useState } from 'react';
import { Typography, CircularProgress, Alert, Button } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import AuthPageShell from '@/components/auth/AuthPageShell';

const BUTTON_HOVER = '#3aabcf'; // Intentional: auth form button hover

export default function VerifyEmailPage() {
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

        if (data.session_token) {
          await signIn('credentials', {
            session_token: data.session_token,
            refresh_token: data.refresh_token || '',
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
          <Typography
            sx={{
              fontSize: 24,
              fontWeight: 700,
              color: 'secondary.dark',
              textAlign: 'center',
              letterSpacing: '-0.02em',
            }}
          >
            Email verified!
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            {message}
          </Typography>
          <Button
            variant="contained"
            href="/architect"
            fullWidth
            sx={{
              mt: 1,
              height: 46,
              borderRadius: '10px',
              bgcolor: 'primary.main',
              '&:hover': {
                bgcolor: BUTTON_HOVER,
                boxShadow: '0 4px 12px rgba(80,185,224,0.3)',
              },
            }}
          >
            Go to dashboard
          </Button>
        </>
      )}

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: 48, color: 'error.main' }} />
          <Typography
            sx={{
              fontSize: 24,
              fontWeight: 700,
              color: 'secondary.dark',
              textAlign: 'center',
              letterSpacing: '-0.02em',
            }}
          >
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
