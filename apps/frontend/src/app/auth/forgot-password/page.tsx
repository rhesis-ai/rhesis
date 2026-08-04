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
import { useAuthStyles } from '@/components/auth/useAuthStyles';

export default function ForgotPasswordPage() {
  const { tokens, heading, subheading, primaryButton, field } = useAuthStyles();
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
          <EmailIcon sx={{ fontSize: 48, color: tokens.accent }} />
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Check your email
          </Typography>
          <Typography sx={{ ...subheading, textAlign: 'center' }}>
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
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Forgot your password?
          </Typography>
          <Typography sx={{ ...subheading, textAlign: 'center', mb: 2 }}>
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
              sx={field}
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
              sx={primaryButton}
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
