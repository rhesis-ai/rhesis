'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  IconButton,
  InputAdornment,
} from '@mui/material';
import LockResetIcon from '@mui/icons-material/LockResetOutlined';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { useSearchParams } from 'next/navigation';
import { ThemeProvider } from '@mui/material/styles';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { DEFAULT_PASSWORD_POLICY, validatePassword } from '@/utils/validation';
import AuthPageShell from '@/components/auth/AuthPageShell';
import BackgroundDecoration from '@/components/auth/BackgroundDecoration';
import { lightTheme } from '@/styles/theme';

const SUBTLE_TEXT = '#6B7280'; // Intentional: auth form subtle text
const BUTTON_HOVER = '#3aabcf'; // Intentional: auth form button hover

interface PasswordPolicy {
  min_length: number;
  max_length: number;
  min_strength_score: number;
}

export default function ResetPasswordPage() {
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

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const confirmPasswordInputRef = useRef<HTMLInputElement>(null);

  const handleTogglePasswordVisibility = () => {
    const input = passwordInputRef.current;
    const cursorPosition = input?.selectionStart ?? 0;
    setShowPassword(!showPassword);
    setTimeout(() => {
      if (input) {
        input.setSelectionRange(cursorPosition, cursorPosition);
      }
    }, 0);
  };

  const handleToggleConfirmPasswordVisibility = () => {
    const input = confirmPasswordInputRef.current;
    const cursorPosition = input?.selectionStart ?? 0;
    setShowConfirmPassword(!showConfirmPassword);
    setTimeout(() => {
      if (input) {
        input.setSelectionRange(cursorPosition, cursorPosition);
      }
    }, 0);
  };

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
        if (response.status === 429) {
          throw new Error(
            'Too many attempts. Please wait a while before trying again.'
          );
        }
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
      <ThemeProvider theme={lightTheme}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            gap: 2,
            bgcolor: 'background.default',
            position: 'relative',
          }}
        >
          <BackgroundDecoration />
          <Box sx={{ position: 'relative', zIndex: 10 }}>
            <Alert severity="error">Invalid or missing reset token.</Alert>
            <Button variant="text" href="/" sx={{ mt: 2 }}>
              Back to sign in
            </Button>
          </Box>
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <AuthPageShell>
      {success ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            alignItems: 'center',
          }}
        >
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
            Password reset!
          </Typography>
          <Typography
            sx={{
              fontSize: 14,
              color: SUBTLE_TEXT,
              textAlign: 'center',
            }}
          >
            Your password has been updated. You can now sign in with your new
            password.
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
            Sign in
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
          <Box sx={{ textAlign: 'center', mb: 0 }}>
            <LockResetIcon
              sx={{ fontSize: 48, color: 'primary.main', mb: 1 }}
            />
            <Typography
              sx={{
                fontSize: 24,
                fontWeight: 700,
                color: 'secondary.dark',
                letterSpacing: '-0.02em',
              }}
            >
              Set a new password
            </Typography>
          </Box>

          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
          >
            <TextField
              label="New password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              fullWidth
              size="small"
              autoComplete="new-password"
              helperText={`Minimum ${passwordPolicy?.min_length ?? 12} characters`}
              inputRef={passwordInputRef}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle password visibility"
                      onClick={handleTogglePasswordVisibility}
                      edge="end"
                      size="small"
                    >
                      {showPassword ? (
                        <VisibilityOffIcon />
                      ) : (
                        <VisibilityIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Confirm password"
              type={showConfirmPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              fullWidth
              size="small"
              autoComplete="new-password"
              inputRef={confirmPasswordInputRef}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle confirm password visibility"
                      onClick={handleToggleConfirmPasswordVisibility}
                      edge="end"
                      size="small"
                    >
                      {showConfirmPassword ? (
                        <VisibilityOffIcon />
                      ) : (
                        <VisibilityIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
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
                loading ? <CircularProgress size={20} /> : <LockResetIcon />
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
              Reset password
            </Button>
          </Box>
        </Box>
      )}
    </AuthPageShell>
  );
}
