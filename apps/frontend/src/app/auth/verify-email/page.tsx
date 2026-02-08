'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

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

        // Refresh the session with the new token so is_email_verified
        // is reflected immediately (hides the verification banner).
        if (data.session_token) {
          await signIn('credentials', {
            session_token: data.session_token,
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
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2,
        p: 3,
        bgcolor: 'background.default',
      }}
    >
      {status === 'loading' && (
        <>
          <CircularProgress />
          <Typography variant="body1">{message}</Typography>
        </>
      )}

      {status === 'success' && (
        <>
          <CheckCircleIcon sx={{ fontSize: 64, color: 'success.main' }} />
          <Typography variant="h5" align="center">
            Email verified!
          </Typography>
          <Typography variant="body1" color="text.secondary" align="center">
            {message}
          </Typography>
          <Button variant="contained" href="/dashboard" sx={{ mt: 2 }}>
            Go to dashboard
          </Button>
        </>
      )}

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: 64, color: 'error.main' }} />
          <Typography variant="h5" align="center">
            Verification failed
          </Typography>
          <Alert severity="error" sx={{ maxWidth: 400 }}>
            {message}
          </Alert>
          <Button variant="text" href="/" sx={{ mt: 2 }}>
            Back to sign in
          </Button>
        </>
      )}
    </Box>
  );
}
