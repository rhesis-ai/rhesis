'use client';

import * as React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
import AuthPageShell from '../components/auth/AuthPageShell';
import { getBaseUrl } from '../utils/url-resolver';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchOutlined';
import { useQuickStart } from '@/contexts/QuickStartContext';
import {
  isAuthenticated,
  isSessionLoading,
  isSessionUnauthenticated,
} from '@/hooks/useIsAuthenticated';
import { scaledVh } from '@/styles/viewport-scaling';
import { rem } from '@/styles/theme-constants';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<
    boolean | null
  >(null);
  const [autoLoggingIn, setAutoLoggingIn] = useState(false);
  const isQuickStartMode = useQuickStart();
  // Whether this visit follows a sign-out, which holds off Quick Start's
  // automatic sign-in. Read once, on arrival: the effect below strips the URL
  // flags before the session finishes loading.
  const holdAutoLogin = useRef<boolean | null>(null);
  // React runs effects twice in development; a second local-login would
  // spend a second single-use auth code.
  const autoLoginStarted = useRef(false);

  const startLocalLogin = useCallback(() => {
    if (autoLoginStarted.current) return;
    autoLoginStarted.current = true;
    setAutoLoggingIn(true);

    fetch(`${getBaseUrl()}/auth/local-login`, {
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
          autoLoginStarted.current = false;
          setAutoLoggingIn(false);
        }
      })
      .catch(error => {
        console.error('Local auto-login error:', error);
        autoLoginStarted.current = false;
        setAutoLoggingIn(false);
      });
  }, []);

  useEffect(() => {
    if (holdAutoLogin.current === null) {
      const urlParams = new URLSearchParams(window.location.search);
      holdAutoLogin.current =
        urlParams.get('session_expired') === 'true' ||
        urlParams.get('force_logout') === 'true';
    }
    if (
      isQuickStartMode &&
      isSessionUnauthenticated(status) &&
      !holdAutoLogin.current
    ) {
      startLocalLogin();
    }
  }, [isQuickStartMode, status, startLocalLogin]);

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
            await fetch(`${getBaseUrl()}/auth/logout`, {
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
          height: scaledVh(),
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
          height: scaledVh(),
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
            <RocketLaunchIcon
              sx={{ fontSize: rem(28), color: 'primary.main' }}
            />
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
