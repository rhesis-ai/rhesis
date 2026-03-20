'use client';

import * as React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
import AuthPageShell from '../components/auth/AuthPageShell';
import { getClientApiBaseUrl } from '../utils/url-resolver';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchOutlined';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<
    boolean | null
  >(null);
  const [autoLoggingIn, setAutoLoggingIn] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isQuickStartMode, setIsQuickStartMode] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    import('@/utils/quick_start').then(({ isQuickStartEnabled }) => {
      setIsQuickStartMode(isQuickStartEnabled());
    });
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    import('@/utils/quick_start').then(({ isQuickStartEnabled }) => {
      const quickStartEnabled = isQuickStartEnabled();

      if (quickStartEnabled && status === 'unauthenticated' && !autoLoggingIn) {
        const urlParams = new URLSearchParams(window.location.search);
        const isSessionExpired = urlParams.get('session_expired') === 'true';
        const isForcedLogout = urlParams.get('force_logout') === 'true';

        if (!isSessionExpired && !isForcedLogout) {
          setAutoLoggingIn(true);

          fetch(`${getClientApiBaseUrl()}/auth/local-login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          })
            .then(async response => {
              if (response.ok) {
                const data = await response.json();
                const { signIn } = await import('next-auth/react');
                await signIn('credentials', {
                  session_token: data.session_token,
                  refresh_token: data.refresh_token || '',
                  redirect: true,
                  callbackUrl: '/dashboard',
                });
              } else {
                console.error('Local auto-login failed');
                setAutoLoggingIn(false);
              }
            })
            .catch(error => {
              console.error('Local auto-login error:', error);
              setAutoLoggingIn(false);
            });
        }
      }
    });
  }, [mounted, status, autoLoggingIn]);

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
          const response = await fetch(`${getClientApiBaseUrl()}/auth/verify`, {
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
            await fetch(`${getClientApiBaseUrl()}/auth/logout`, {
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

  if (status === 'loading' || autoLoggingIn) {
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
        {autoLoggingIn && (
          <Typography variant="body2" color="text.secondary">
            Logging in...
          </Typography>
        )}
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
