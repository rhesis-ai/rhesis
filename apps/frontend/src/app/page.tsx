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
import { fetchQuickStartEnabled } from '@/utils/quick_start';
import {
  isAuthenticated,
  isSessionLoading,
  isSessionUnauthenticated,
} from '@/hooks/useIsAuthenticated';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<
    boolean | null
  >(null);
  const [autoLoggingIn, setAutoLoggingIn] = useState(false);
  const [isQuickStartMode, setIsQuickStartMode] = useState(false);
  const [quickStartLoaded, setQuickStartLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    fetchQuickStartEnabled().then(enabled => {
      if (!cancelled) {
        setIsQuickStartMode(enabled);
        setQuickStartLoaded(true);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (
      quickStartLoaded &&
      isQuickStartMode &&
      isSessionUnauthenticated(status) &&
      !autoLoggingIn
    ) {
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
                code: data.auth_code,
                redirect: true,
                callbackUrl: '/architect',
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
  }, [quickStartLoaded, isQuickStartMode, status, autoLoggingIn]);

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

      if (isAuthenticated(status)) {
        signOut({ redirect: false, callbackUrl: '/' });
      }
      return;
    }

    if (
      isAuthenticated(status) &&
      session &&
      !sessionExpired &&
      backendSessionValid === null
    ) {
      // The access token never reaches this client component (BFF proxy
      // injects it server-side), so we can no longer POST it to /auth/verify
      // directly. `session.error` is the equivalent signal: the `jwt`
      // callback already sets it whenever a refresh attempt fails, which
      // only happens when the backend has actually rejected the refresh
      // token — the same condition /auth/verify used to detect explicitly.
      if (session.error) {
        (async () => {
          try {
            await fetch(`${getClientApiBaseUrl()}/auth/logout`, {
              method: 'GET',
              headers: { Accept: 'application/json' },
            });
          } catch (_logoutError) {
            // Ignore — signOut below still clears the local session.
          }

          setBackendSessionValid(false);
          setSessionExpired(true);
          signOut({ redirect: false, callbackUrl: '/' });
        })();
      } else {
        setBackendSessionValid(true);
        router.replace('/architect');
      }
    }
  }, [session, status, router, sessionExpired, backendSessionValid]);

  if (isSessionLoading(status) || autoLoggingIn) {
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
    isAuthenticated(status) &&
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
