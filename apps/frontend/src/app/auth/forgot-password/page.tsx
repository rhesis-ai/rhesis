'use client';

import { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import EmailIcon from '@mui/icons-material/EmailOutlined';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import AuthPageShell from '@/components/auth/AuthPageShell';

const SUBTLE_TEXT = '#6B7280'; // Intentional: auth form subtle text
const BUTTON_HOVER = '#3aabcf'; // Intentional: auth form button hover

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${getClientApiBaseUrl()}/auth/forgot-password`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Something went wrong');
      }

      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthPageShell>
      {submitted ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            alignItems: 'center',
          }}
        >
          <EmailIcon sx={{ fontSize: 48, color: 'primary.main' }} />
          <Typography
            sx={{
              fontSize: 24,
              fontWeight: 700,
              color: 'secondary.dark',
              textAlign: 'center',
              letterSpacing: '-0.02em',
            }}
          >
            Check your email
          </Typography>
          <Typography
            sx={{
              fontSize: 14,
              color: SUBTLE_TEXT,
              textAlign: 'center',
            }}
          >
            If an account exists for <strong>{email}</strong>, we&apos;ve sent a
            password reset link. Check your inbox and spam folder.
          </Typography>
          <Button
            variant="text"
            href="/"
            sx={{ mt: 1 }}
            startIcon={<ArrowBackIcon />}
          >
            Back to sign in
          </Button>
        </Box>
      ) : (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <Typography
            sx={{
              fontSize: 24,
              fontWeight: 700,
              color: 'secondary.dark',
              textAlign: 'center',
              letterSpacing: '-0.02em',
              mb: 0,
            }}
          >
            Forgot your password?
          </Typography>
          <Typography
            sx={{
              fontSize: 14,
              color: SUBTLE_TEXT,
              textAlign: 'center',
              mb: 2,
            }}
          >
            Enter your email and we&apos;ll send you a reset link.
          </Typography>

          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              fullWidth
              size="small"
              autoComplete="email"
              autoFocus
            />
            {error && (
              <Alert severity="error" sx={{ py: 0 }}>
                {error}
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading}
              startIcon={
                loading ? <CircularProgress size={20} /> : <EmailIcon />
              }
              sx={{
                height: 46,
                borderRadius: '10px', // Intentional: button border radius
                bgcolor: 'primary.main',
                '&:hover': {
                  bgcolor: BUTTON_HOVER,
                  boxShadow: '0 4px 12px rgba(80,185,224,0.3)', // Intentional: button hover glow
                },
              }}
            >
              Send reset link
            </Button>
            <Button
              variant="text"
              href="/"
              startIcon={<ArrowBackIcon />}
              sx={{ alignSelf: 'center', color: 'text.secondary' }}
            >
              Back to sign in
            </Button>
          </Box>
        </Box>
      )}
    </AuthPageShell>
  );
}
