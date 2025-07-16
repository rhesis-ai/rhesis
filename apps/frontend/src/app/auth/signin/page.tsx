'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CircularProgress, Box, Typography } from '@mui/material';
import { clearAllSessionData } from '@/utils/session';

export default function SignIn() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>('Hang tight...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuth = async () => {
      try {
        console.log('🟢 [DEBUG] SignIn page - handleAuth called');
        console.log('🟢 [DEBUG] Search params:', Object.fromEntries(searchParams.entries()));
        
        // Check for session expiration error
        const errorParam = searchParams.get('error');
        const postLogout = searchParams.get('post_logout');
        
        console.log('🟢 [DEBUG] Error param:', errorParam, 'Post logout:', postLogout);
        
        if (errorParam === 'session_expired') {
          console.log('🟢 [DEBUG] Session expired detected, redirecting to home');
          // Redirect to home page for expired sessions
          window.location.href = '/';
          return;
        }

        if (postLogout === 'true') {
          console.log('🟢 [DEBUG] Post logout redirect detected, redirecting to home');
          // Redirect to home page after logout
          window.location.href = '/';
          return;
        }

        const incomingToken = searchParams.get('session_token');
        
        if (incomingToken) {
          console.log('🟢 [DEBUG] Incoming session token detected, setting cookie');
          setStatus('Verifying session token...');
          
          // Set cookie with proper domain
          const cookieOptions = process.env.NODE_ENV === 'production' 
            ? `domain=rhesis.ai; path=/; secure; samesite=lax`
            : 'path=/; samesite=lax';
            
          document.cookie = `next-auth.session-token=${incomingToken}; ${cookieOptions}`;
          
          setStatus('Authentication successful, redirecting...');
          const returnTo = searchParams.get('return_to') || '/dashboard';
          console.log('🟢 [DEBUG] Redirecting to:', returnTo);
          window.location.href = returnTo;
          return;
        }

        // If no token and no special parameters, redirect to home page for unified login experience
        const returnTo = searchParams.get('return_to');
        setStatus('Redirecting to login...');

        // Redirect to home page which has the unified login experience
        console.log('🟢 [DEBUG] No token found, redirecting to home page for unified login');
        const homeUrl = new URL('/', window.location.origin);
        if (returnTo) {
          homeUrl.searchParams.set('return_to', returnTo);
        }
        window.location.replace(homeUrl.toString());

      } catch (error) {
        const err = error as Error;
        console.error('🟢 [DEBUG] Auth error:', err);
        setError(`Authentication error: ${err.message}`);
      }
    };

    handleAuth();
  }, [searchParams]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2,
        bgcolor: 'background.default',
      }}
    >
      <CircularProgress />
      <Typography variant="body1" align="center">
        {status}
      </Typography>
      {error && (
        <Typography color="error" align="center">
          {error}
        </Typography>
      )}
    </Box>
  );
}