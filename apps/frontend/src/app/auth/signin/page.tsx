'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CircularProgress, Box, Typography } from '@mui/material';
import { clearAllSessionData } from '@/utils/session';

export default function SignIn() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>('Hang on...');
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
          console.log('🟢 [DEBUG] Session expired detected, calling clearAllSessionData');
          // Clear all session data if session has expired
          clearAllSessionData();
          return; // clearAllSessionData will handle the redirect
        }

        if (postLogout === 'true') {
          console.log('🟢 [DEBUG] Post logout redirect detected');
          setStatus('Logout successful. Please sign in again.');
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

        // If no token, redirect to backend login
        console.log('🟢 [DEBUG] No token found, redirecting to backend login');
        setStatus('Redirecting to login...');
        const currentUrl = window.location.href;
        window.location.replace(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login?return_to=${encodeURIComponent(currentUrl)}`
        );

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