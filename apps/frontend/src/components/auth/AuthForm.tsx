'use client';

import {
  Box,
  Typography,
  Paper,
  Button,
  Divider,
  Checkbox,
  FormControlLabel,
  TextField,
  CircularProgress,
  Alert,
} from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import GitHubIcon from '@mui/icons-material/GitHub';
import EmailIcon from '@mui/icons-material/Email';
import { useState, useEffect } from 'react';
import { signIn } from 'next-auth/react';
import { getClientApiBaseUrl } from '../../utils/url-resolver';

interface ProviderInfo {
  name: string;
  display_name: string;
  type: 'oauth' | 'credentials';
  enabled: boolean;
  registration_enabled?: boolean;
}

interface AuthFormProps {
  /** If true, show registration form instead of login */
  isRegistration?: boolean;
}

export default function AuthForm({ isRegistration = false }: AuthFormProps) {
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTermsWarning, setShowTermsWarning] = useState(false);
  const [previouslyAccepted, setPreviouslyAccepted] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Email/password form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Magic link state
  const [showMagicLink, setShowMagicLink] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);

  // Check local storage for previous acceptance on component mount
  useEffect(() => {
    const hasAcceptedTerms = localStorage.getItem('termsAccepted') === 'true';
    if (hasAcceptedTerms) {
      setTermsAccepted(true);
      setPreviouslyAccepted(true);
    }
  }, []);

  // Fetch available providers from backend
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const response = await fetch(`${getClientApiBaseUrl()}/auth/providers`);
        if (!response.ok) {
          throw new Error('Failed to fetch providers');
        }
        const data = await response.json();
        setProviders(data.providers || []);
      } catch (err) {
        console.error('Error fetching providers:', err);
        setError('Failed to load authentication options');
      } finally {
        setLoading(false);
      }
    };

    fetchProviders();
  }, []);

  const handleTermsAcceptance = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const accepted = event.target.checked;
    setTermsAccepted(accepted);
    if (accepted) {
      localStorage.setItem('termsAccepted', 'true');
      setShowTermsWarning(false);
    }
  };

  const checkTerms = (): boolean => {
    if (!termsAccepted) {
      setShowTermsWarning(true);
      return false;
    }
    setShowTermsWarning(false);
    return true;
  };

  const handleOAuthLogin = async (providerName: string) => {
    if (!checkTerms()) return;

    // Get return_to from URL params or default to dashboard
    const searchParams = new URLSearchParams(window.location.search);
    const returnTo = searchParams.get('return_to') || '/dashboard';

    // Redirect to backend OAuth endpoint
    const loginUrl = new URL(
      `${getClientApiBaseUrl()}/auth/login/${providerName}`
    );
    loginUrl.searchParams.set('return_to', returnTo);

    window.location.href = loginUrl.toString();
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkTerms()) return;

    setFormLoading(true);
    setFormError(null);

    try {
      const endpoint = isRegistration
        ? `${getClientApiBaseUrl()}/auth/register`
        : `${getClientApiBaseUrl()}/auth/login/email`;

      const body = isRegistration
        ? { email, password, name: name || undefined }
        : { email, password };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        credentials: 'include',
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }

      // Use NextAuth to establish session with the token from backend
      if (data.session_token) {
        const result = await signIn('credentials', {
          session_token: data.session_token,
          redirect: false,
        });

        if (result?.error) {
          throw new Error(result.error);
        }

        // Redirect to dashboard or return_to URL
        const searchParams = new URLSearchParams(window.location.search);
        const returnTo = searchParams.get('return_to') || '/dashboard';
        window.location.href = returnTo;
      }
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Authentication failed'
      );
    } finally {
      setFormLoading(false);
    }
  };

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkTerms()) return;

    setFormLoading(true);
    setFormError(null);

    try {
      const response = await fetch(`${getClientApiBaseUrl()}/auth/magic-link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to send magic link');
      }

      setMagicLinkSent(true);
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to send magic link'
      );
    } finally {
      setFormLoading(false);
    }
  };

  const getProviderIcon = (providerName: string) => {
    switch (providerName) {
      case 'google':
        return <GoogleIcon />;
      case 'github':
        return <GitHubIcon />;
      case 'email':
        return <EmailIcon />;
      default:
        return null;
    }
  };

  const oauthProviders = providers.filter(p => p.type === 'oauth' && p.enabled);
  const emailProvider = providers.find(p => p.name === 'email' && p.enabled);
  const registrationEnabled = emailProvider?.registration_enabled ?? false;

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 4,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Paper
        elevation={0}
        sx={{
          p: 3,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <Typography variant="h6" align="center">
          {isRegistration
            ? 'Create your account'
            : 'All paws on deck for testing!'}
        </Typography>

        {/* Email/Password Form */}
        {emailProvider && !showMagicLink && !magicLinkSent && (
          <Box
            component="form"
            onSubmit={handleEmailSubmit}
            sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
          >
            {isRegistration && (
              <TextField
                label="Name"
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                fullWidth
                size="small"
                autoComplete="name"
              />
            )}
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              fullWidth
              size="small"
              autoComplete="email"
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              fullWidth
              size="small"
              autoComplete={
                isRegistration ? 'new-password' : 'current-password'
              }
              helperText={isRegistration ? 'Minimum 8 characters' : undefined}
            />
            {formError && (
              <Alert severity="error" sx={{ py: 0 }}>
                {formError}
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="medium"
              disabled={formLoading}
              startIcon={
                formLoading ? <CircularProgress size={20} /> : <EmailIcon />
              }
            >
              {isRegistration ? 'Create Account' : 'Sign in with Email'}
            </Button>

            {/* Forgot password and magic link (login only) */}
            {!isRegistration && (
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Typography variant="body2">
                  <a
                    href="/auth/forgot-password"
                    style={{ color: 'inherit', textDecoration: 'none' }}
                  >
                    Forgot password?
                  </a>
                </Typography>
                <Typography variant="body2">
                  <a
                    href="#"
                    onClick={e => {
                      e.preventDefault();
                      setShowMagicLink(true);
                    }}
                    style={{ color: 'inherit', textDecoration: 'none' }}
                  >
                    Sign in with magic link
                  </a>
                </Typography>
              </Box>
            )}

            {/* Toggle between login and registration */}
            {registrationEnabled && (
              <Typography
                variant="body2"
                align="center"
                sx={{ color: 'text.secondary' }}
              >
                {isRegistration ? (
                  <>
                    Already have an account?{' '}
                    <a href="/" style={{ color: 'inherit' }}>
                      Sign in
                    </a>
                  </>
                ) : (
                  <>
                    Don&apos;t have an account?{' '}
                    <a href="/auth/register" style={{ color: 'inherit' }}>
                      Register
                    </a>
                  </>
                )}
              </Typography>
            )}
          </Box>
        )}

        {/* Magic Link Form */}
        {emailProvider && showMagicLink && !magicLinkSent && (
          <Box
            component="form"
            onSubmit={handleMagicLink}
            sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
          >
            <Typography variant="body2" color="text.secondary" align="center">
              Enter your email and we&apos;ll send you a link to sign in
              instantly.
            </Typography>
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
            {formError && (
              <Alert severity="error" sx={{ py: 0 }}>
                {formError}
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="medium"
              disabled={formLoading}
              startIcon={
                formLoading ? <CircularProgress size={20} /> : <EmailIcon />
              }
            >
              Send magic link
            </Button>
            <Typography variant="body2" align="center">
              <a
                href="#"
                onClick={e => {
                  e.preventDefault();
                  setShowMagicLink(false);
                  setFormError(null);
                }}
                style={{ color: 'inherit', textDecoration: 'none' }}
              >
                Sign in with password instead
              </a>
            </Typography>
          </Box>
        )}

        {/* Magic Link Sent Confirmation */}
        {magicLinkSent && (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              alignItems: 'center',
            }}
          >
            <EmailIcon sx={{ fontSize: 48, color: 'primary.main' }} />
            <Typography variant="body1" align="center">
              Check your email!
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center">
              We&apos;ve sent a sign-in link to <strong>{email}</strong>. Click
              the link in the email to sign in.
            </Typography>
            <Button
              variant="text"
              size="small"
              onClick={() => {
                setMagicLinkSent(false);
                setShowMagicLink(false);
                setFormError(null);
              }}
            >
              Back to sign in
            </Button>
          </Box>
        )}

        {/* OAuth Providers */}
        {oauthProviders.length > 0 && (
          <>
            {emailProvider && (
              <Divider>
                <Typography color="textSecondary" variant="body2">
                  Or continue with
                </Typography>
              </Divider>
            )}

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {oauthProviders.map(provider => (
                <Button
                  key={provider.name}
                  variant="outlined"
                  fullWidth
                  size="medium"
                  startIcon={getProviderIcon(provider.name)}
                  onClick={() => handleOAuthLogin(provider.name)}
                  sx={{
                    color: theme => theme.palette.text.primary,
                  }}
                >
                  Continue with {provider.display_name}
                </Button>
              ))}
            </Box>
          </>
        )}

        {/* Terms Warning */}
        {showTermsWarning && (
          <Typography variant="body2" color="error" sx={{ mt: 1 }}>
            Please accept the Terms and Conditions to continue.
          </Typography>
        )}

        {/* Terms and Conditions */}
        {previouslyAccepted ? (
          <Typography
            variant="body2"
            align="center"
            sx={{ mt: 1, color: 'text.secondary' }}
          >
            By continuing, you confirm your agreement to our&nbsp;
            <a
              href="https://www.rhesis.ai/terms-conditions"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit' }}
            >
              Terms and Conditions
            </a>
            &nbsp;&amp;&nbsp;
            <a
              href="https://www.rhesis.ai/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit' }}
            >
              Privacy Policy
            </a>
            .
          </Typography>
        ) : (
          <FormControlLabel
            control={
              <Checkbox
                checked={termsAccepted}
                onChange={handleTermsAcceptance}
                color="primary"
              />
            }
            label={
              <Typography variant="body2">
                By signing in you are agreeing to our&nbsp;
                <a
                  href="https://www.rhesis.ai/terms-conditions"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'inherit' }}
                >
                  Terms and Conditions
                </a>
                &nbsp;&amp;&nbsp;
                <a
                  href="https://www.rhesis.ai/privacy-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'inherit' }}
                >
                  Privacy Policy
                </a>
                .
              </Typography>
            }
            sx={{ mt: 1 }}
          />
        )}
      </Paper>
    </Box>
  );
}
