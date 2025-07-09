'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CircularProgress, Box, Typography, Container } from '@mui/material';
import { clearAllSessionData } from '@/utils/session';

export default function SignIn() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>('Initializing...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuth = async () => {
      try {
        // Check for session expiration error
        const errorParam = searchParams.get('error');
        if (errorParam === 'session_expired') {
          // Clear all session data if session has expired
          clearAllSessionData();
          return; // clearAllSessionData will handle the redirect
        }

        const incomingToken = searchParams.get('session_token');
        
        if (incomingToken) {
          setStatus('Verifying session token...');
          
          // Set cookie with proper domain
          const cookieOptions = process.env.NODE_ENV === 'production' 
            ? `domain=rhesis.ai; path=/; secure; samesite=lax`
            : 'path=/; samesite=lax';
            
          document.cookie = `next-auth.session-token=${incomingToken}; ${cookieOptions}`;
          
          setStatus('Authentication successful, redirecting...');
          const returnTo = searchParams.get('return_to') || '/dashboard';
          window.location.href = returnTo;
          return;
        }

        // If no token, redirect to backend login
        setStatus('Redirecting to login...');
        const currentUrl = window.location.href;
        window.location.replace(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login?return_to=${encodeURIComponent(currentUrl)}`
        );

      } catch (error) {
        const err = error as Error;
        setError(`Authentication error: ${err.message}`);
        console.error('Auth error:', err);
      }
    };

    handleAuth();
  }, [searchParams]);

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          mt: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="h6" align="center">
          {status}
        </Typography>
        {error && (
          <Typography color="error" align="center">
            {error}
          </Typography>
        )}
      </Box>
    </Container>
  );
}