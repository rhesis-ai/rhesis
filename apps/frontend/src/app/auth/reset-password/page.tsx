'use client';

import { useState, useEffect } from 'react';
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
import LockResetIcon from '@mui/icons-material/LockResetOutlined';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import { useSearchParams } from 'next/navigation';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { DEFAULT_PASSWORD_POLICY, validatePassword } from '@/utils/validation';

interface PasswordPolicy {
  min_length: number;
  max_length: number;
}

export default function ResetPasswordPage() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordPolicy, setPasswordPolicy] = useState<PasswordPolicy | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPolicy = async () => {
      try {
        const res = await fetch(`${getClientApiBaseUrl()}/auth/providers`);
        if (res.ok) {
          const data = await res.json();
          setPasswordPolicy(data.password_policy || null);
        }
      } catch {
        // Use default policy on fetch failure
      }
    };
    fetchPolicy();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    const policy = passwordPolicy ?? DEFAULT_PASSWORD_POLICY;
    const result = validatePassword(password, policy);
    if (!result.isValid) {
      setError(result.message ?? 'Invalid password');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `${getClientApiBaseUrl()}/auth/reset-password`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, new_password: password }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to reset password');
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          gap: 2,
        }}
      >
        <Alert severity="error">Invalid or missing reset token.</Alert>
        <Button variant="text" href="/">
          Back to sign in
        </Button>
      </Box>
    );
  }

  return (
    <Grid container component="main" sx={{ height: '100vh' }}>
      <Grid
        sx={{
          backgroundColor: 'primary.dark',
          display: 'flex',
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
              {success ? (
                <>
                  <Box sx={{ textAlign: 'center', mb: 1 }}>
                    <CheckCircleIcon
                      sx={{ fontSize: 48, color: 'success.main', mb: 1 }}
                    />
                    <Typography variant="h6">Password reset!</Typography>
                  </Box>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    align="center"
                  >
                    Your password has been updated. You can now sign in with
                    your new password.
                  </Typography>
                  <Button variant="contained" href="/" fullWidth sx={{ mt: 2 }}>
                    Sign in
                  </Button>
                </>
              ) : (
                <>
                  <Box sx={{ textAlign: 'center', mb: 1 }}>
                    <LockResetIcon
                      sx={{ fontSize: 48, color: 'primary.main', mb: 1 }}
                    />
                    <Typography variant="h6">Set a new password</Typography>
                  </Box>
                  <Box
                    component="form"
                    onSubmit={handleSubmit}
                    sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
                    <TextField
                      label="New password"
                      type="password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      required
                      fullWidth
                      size="small"
                      autoComplete="new-password"
                      helperText={`Minimum ${passwordPolicy?.min_length ?? 8} characters`}
                    />
                    <TextField
                      label="Confirm password"
                      type="password"
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      required
                      fullWidth
                      size="small"
                      autoComplete="new-password"
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
                        loading ? (
                          <CircularProgress size={20} />
                        ) : (
                          <LockResetIcon />
                        )
                      }
                    >
                      Reset password
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
