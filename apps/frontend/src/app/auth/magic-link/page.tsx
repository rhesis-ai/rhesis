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
import { ThemeProvider } from '@mui/material/styles';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';
import { lightTheme } from '@/styles/theme';

const CARD_BORDER = '#E5E7EB'; // Intentional: auth card border
const BUTTON_HOVER = '#3aabcf'; // Intentional: auth form button hover

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
          const result = await signIn('credentials', {
            session_token: data.session_token,
            refresh_token: data.refresh_token || '',
            redirect: false,
          });

          if (result?.error) {
            throw new Error(result.error);
          }

          const redirectTo = data.user?.organization_id
            ? '/dashboard'
            : '/onboarding';
          window.location.href = redirectTo;
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
    <ThemeProvider theme={lightTheme}>
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
                Back to sign in
              </Button>
            </>
          )}
        </Box>
      </Box>
    </ThemeProvider>
  );
}
