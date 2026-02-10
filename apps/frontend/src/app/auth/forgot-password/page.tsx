'use client';

import { useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import Image from 'next/image';
import EmailIcon from '@mui/icons-material/EmailOutlined';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function ForgotPasswordPage() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
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
    <Grid container component="main" sx={{ height: '100vh' }}>
      {/* Left side - Branding */}
      <Grid
        sx={{
          backgroundColor: 'primary.dark',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        size={{ xs: false, sm: 4, md: 7 }}
      >
        <Image
          src="/logos/rhesis-logo-platypus.png"
          alt="Rhesis AI Logo"
          width={300}
          height={0}
          style={{ height: 'auto' }}
          priority
        />
      </Grid>
      {/* Right side - Form */}
      <Grid
        component={Paper}
        elevation={6}
        square
        size={{ xs: 12, sm: 8, md: 5 }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            p: { xs: 3, sm: 6, md: 8 },
          }}
        >
          {isMobile && (
            <Box sx={{ mb: 4 }}>
              <Image
                src="/logos/rhesis-logo-platypus.png"
                alt="Rhesis AI Logo"
                width={160}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          )}
          <Box sx={{ width: '100%', maxWidth: 400 }}>
            <Paper
              elevation={0}
              sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}
            >
              {submitted ? (
                <>
                  <Box sx={{ textAlign: 'center', mb: 1 }}>
                    <EmailIcon
                      sx={{ fontSize: 48, color: 'primary.main', mb: 1 }}
                    />
                    <Typography variant="h6">Check your email</Typography>
                  </Box>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    align="center"
                  >
                    If an account exists for <strong>{email}</strong>,
                    we&apos;ve sent a password reset link. Check your inbox and
                    spam folder.
                  </Typography>
                  <Button
                    variant="text"
                    href="/"
                    sx={{ mt: 2 }}
                    startIcon={<ArrowBackIcon />}
                  >
                    Back to sign in
                  </Button>
                </>
              ) : (
                <>
                  <Typography variant="h6" align="center">
                    Forgot your password?
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    align="center"
                  >
                    Enter your email address and we&apos;ll send you a link to
                    reset your password.
                  </Typography>
                  <Box
                    component="form"
                    onSubmit={handleSubmit}
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                      mt: 1,
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
                      disabled={loading}
                      startIcon={
                        loading ? <CircularProgress size={20} /> : <EmailIcon />
                      }
                    >
                      Send reset link
                    </Button>
                    <Button
                      variant="text"
                      href="/"
                      startIcon={<ArrowBackIcon />}
                    >
                      Back to sign in
                    </Button>
                  </Box>
                </>
              )}
            </Paper>
          </Box>
        </Box>
      </Grid>
    </Grid>
  );
}
