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
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { DEFAULT_PASSWORD_POLICY, validatePassword } from '@/utils/validation';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { useAuthStyles } from '@/components/auth/useAuthStyles';

interface PasswordPolicy {
  min_length: number;
  max_length: number;
  min_strength_score: number;
}

export default function ResetPasswordPage() {
  const { tokens, heading, subheading, primaryButton, outlinedButton, field } =
    useAuthStyles();
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
      <AuthPageShell>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Reset link not valid
          </Typography>
          <Alert severity="error">Invalid or missing reset token.</Alert>
          <Button variant="outlined" href="/" sx={outlinedButton}>
            Back to sign in
          </Button>
        </Box>
      </AuthPageShell>
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
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Password reset!
          </Typography>
          <Typography sx={{ ...subheading, textAlign: 'center' }}>
            Your password has been updated. You can now sign in with your new
            password.
          </Typography>
          <Button
            variant="contained"
            href="/"
            fullWidth
            sx={{ ...primaryButton, mt: 1 }}
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
            <LockResetIcon sx={{ fontSize: 48, color: tokens.accent, mb: 1 }} />
            <Typography sx={heading}>Set a new password</Typography>
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
              sx={field}
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
              sx={field}
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
                loading ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <LockResetIcon />
                )
              }
              sx={primaryButton}
            >
              Reset password
            </Button>
          </Box>
        </Box>
      )}
    </AuthPageShell>
  );
}
