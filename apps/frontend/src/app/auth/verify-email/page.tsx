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
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';

const CARD_BORDER = '#E5E7EB'; // Intentional: auth card border
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
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        p: 3,
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
          bgcolor: 'background.default',
          border: `1px solid ${CARD_BORDER}`,
          borderRadius: '20px', // Intentional: auth card radius
          p: { xs: '32px 24px', sm: '44px 40px' },
          maxWidth: 420,
          width: '100%',
          boxShadow:
            '0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06), 0 24px 48px rgba(0,0,0,0.04)',
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
              href="/dashboard"
              fullWidth
              sx={{
                mt: 1,
                height: 46,
                borderRadius: '10px', // Intentional: button border radius
                bgcolor: 'primary.main',
                '&:hover': {
                  bgcolor: BUTTON_HOVER,
                  boxShadow: '0 4px 12px rgba(80,185,224,0.3)', // Intentional: button hover glow
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
      </Box>
    </Box>
  );
}
