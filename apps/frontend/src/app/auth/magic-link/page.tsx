'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function MagicLinkPage() {
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

        if (data.session_token) {
          // Use NextAuth to establish session
          const result = await signIn('credentials', {
            session_token: data.session_token,
            redirect: false,
          });

          if (result?.error) {
            throw new Error(result.error);
          }

          // Redirect to dashboard
          window.location.href = '/dashboard';
          return;
        }

        throw new Error('No session token received');
      } catch (err) {
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'Sign-in failed');
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

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: 64, color: 'error.main' }} />
          <Typography variant="h5" align="center">
            Sign-in failed
          </Typography>
          <Alert severity="error" sx={{ maxWidth: 400 }}>
            {message}
          </Alert>
          <Typography variant="body2" color="text.secondary" align="center">
            The magic link may have expired. Please request a new one.
          </Typography>
          <Button variant="contained" href="/" sx={{ mt: 2 }}>
            Back to sign in
          </Button>
        </>
      )}
    </Box>
  );
}
