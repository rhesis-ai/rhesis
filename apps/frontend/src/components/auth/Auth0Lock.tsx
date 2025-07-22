'use client';

import { Box, Typography, Paper, Button, Divider, Checkbox, FormControlLabel } from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import GitHubIcon from '@mui/icons-material/GitHub';
import AppleIcon from '@mui/icons-material/Apple';
import MicrosoftIcon from '@mui/icons-material/Window';
import { useState, useEffect } from 'react';

interface Props {
  clientId: string;
  domain: string;
}

export default function CustomAuthForm({ clientId, domain }: Props) {
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTermsWarning, setShowTermsWarning] = useState(false);
  const [previouslyAccepted, setPreviouslyAccepted] = useState(false);

  // Check local storage for previous acceptance on component mount
  useEffect(() => {
    const hasAcceptedTerms = localStorage.getItem('termsAccepted') === 'true';
    if (hasAcceptedTerms) {
      setTermsAccepted(true);
      setPreviouslyAccepted(true);
    }
  }, []);

  const handleTermsAcceptance = (event: React.ChangeEvent<HTMLInputElement>) => {
    const accepted = event.target.checked;
    setTermsAccepted(accepted);
    if (accepted) {
      localStorage.setItem('termsAccepted', 'true');
      setShowTermsWarning(false);
    }
  };

  const handleLogin = async (provider?: string) => {
    // Check if terms are accepted
    if (!termsAccepted) {
      setShowTermsWarning(true);
      // Don't proceed with login
      return;
    }
    
    // Reset warning if previously shown
    setShowTermsWarning(false);
    
    const redirectUri = process.env.NEXT_PUBLIC_API_BASE_URL 
      ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`
      : '';
    
    if (!redirectUri) {
      console.error('API URL environment variable is not defined');
      return;
    }

    // Create URL with search params
    const loginUrl = new URL(redirectUri);
    if (provider) {
      loginUrl.searchParams.set('connection', provider);
    }
    
    // Get return_to from URL params or default to dashboard
    const searchParams = new URLSearchParams(window.location.search);
    const returnTo = searchParams.get('return_to') || '/dashboard';
    loginUrl.searchParams.set('return_to', returnTo);

    // Redirect to backend login
    window.location.href = loginUrl.toString();
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Paper 
        elevation={0} 
        sx={{ 
          p: 3,
          display: 'flex',
          flexDirection: 'column',
          gap: 2
        }}
      >
        <Typography variant="h6" align="center">
          Sign In
        </Typography>

        <Button
          variant="contained"
          fullWidth
          size="medium"
          onClick={() => handleLogin()}
        >
          Sign in with Email
        </Button>

        <Divider>
          <Typography color="textSecondary" variant="body2">
            Or continue with
          </Typography>
        </Divider>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Button
            variant="outlined"
            fullWidth
            size="medium"
            startIcon={<GoogleIcon />}
            onClick={() => handleLogin('google-oauth2')}
          >
            Continue with Google
          </Button>

          <Button
            variant="outlined"
            fullWidth
            size="medium"
            startIcon={<GitHubIcon />}
            onClick={() => handleLogin('github')}
          >
            Continue with GitHub
          </Button>

          <Button
            variant="outlined"
            fullWidth
            size="medium"
            startIcon={<AppleIcon />}
            onClick={() => handleLogin('apple')}
          >
            Continue with Apple
          </Button>

          <Button
            variant="outlined"
            fullWidth
            size="medium"
            startIcon={<MicrosoftIcon />}
            onClick={() => handleLogin('windowslive')}
          >
            Continue with Microsoft
          </Button>

          {showTermsWarning && (
            <Typography variant="body2" color="error" sx={{ mt: 1 }}>
              Please accept the Terms and Conditions to continue.
            </Typography>
          )}

          {previouslyAccepted ? (
            <Typography variant="body2" align="center" sx={{ mt: 1, color: 'text.secondary' }}>
              By continuing, you confirm your agreement to our&nbsp;
              <a href="https://www.rhesis.ai/terms-conditions" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>Terms and Conditions</a>&nbsp;&amp;&nbsp;
              <a href="https://www.rhesis.ai/privacy-policy" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>Privacy Policy</a>.
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
                  <a href="https://www.rhesis.ai/terms-conditions" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>Terms and Conditions</a>&nbsp;&amp;&nbsp;
                  <a href="https://www.rhesis.ai/privacy-policy" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>Privacy Policy</a>.
                </Typography>
              }
              sx={{ mt: 1 }}
            />
          )}

        </Box>
      </Paper>
    </Box>
  );
} 