'use client';

import * as React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
import AuthPageShell from '../components/auth/AuthPageShell';
import { getClientUpstreamApiBaseUrl } from '../utils/url-resolver';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchOutlined';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<
    boolean | null
  >(null);
  const [mounted, setMounted] = useState(false);
  const [isQuickStartMode, setIsQuickStartMode] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    import('@/utils/quick_start').then(({ isQuickStartHostAllowed }) => {
      setIsQuickStartMode(isQuickStartHostAllowed());
    });
  }, [mounted]);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const isSessionExpired = urlParams.get('session_expired') === 'true';
    const isForcedLogout = urlParams.get('force_logout') === 'true';

    if (isSessionExpired || isForcedLogout) {
      setSessionExpired(true);
      setBackendSessionValid(false);
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('session_expired');
      newUrl.searchParams.delete('force_logout');
      window.history.replaceState({}, '', newUrl.toString());

      if (status === 'authenticated') {
        signOut({ redirect: false, callbackUrl: '/' });
      }
      return;
    }

    if (
      status === 'authenticated' &&
      session &&
      !sessionExpired &&
      backendSessionValid === null
    ) {
      const validateBackendSession = async () => {
        try {
          const response = await fetch(`${getClientUpstreamApiBaseUrl()}/auth/verify`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/json',
            },
            body: JSON.stringify({ session_token: session.session_token }),
          });

          if (response.ok) {
            const data = await response.json();
            if (data.authenticated && data.user) {
              setBackendSessionValid(true);
              router.replace('/dashboard');
              return;
            }
          }

          try {
            await fetch(`${getClientUpstreamApiBaseUrl()}/auth/logout`, {
              method: 'GET',
              headers: { Accept: 'application/json' },
            });
          } catch (_logoutError) {}

          setBackendSessionValid(false);
          setSessionExpired(true);
          signOut({ redirect: false, callbackUrl: '/' });
        } catch (_error) {
          setBackendSessionValid(false);
          setSessionExpired(true);
          signOut({ redirect: false, callbackUrl: '/' });
        }
      };

      validateBackendSession();
    }
  }, [session, status, router, sessionExpired, backendSessionValid]);

  if (status === 'loading') {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (
    status === 'authenticated' &&
    session &&
    !sessionExpired &&
    backendSessionValid === true
  ) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {isQuickStartMode ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <RocketLaunchIcon sx={{ fontSize: 28, color: 'primary.main' }} />
            <Typography variant="h6">Quick Start Mode</Typography>
          </Box>
        ) : (
          <Typography variant="body1" color="text.secondary">
            Welcome back, {session.user?.name || 'User'}! Redirecting...
          </Typography>
        )}
        <CircularProgress />
      </Box>
    );
  }

  return (
    <AuthPageShell>
      <LoginSection />
    </AuthPageShell>
  );
}
