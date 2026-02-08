'use client';

import * as React from 'react';
import {
  Box,
  Container,
  AppBar,
  Toolbar,
  Typography,
  CircularProgress,
  Paper,
  Grid,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import Image from 'next/image';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
import { getClientApiBaseUrl } from '../utils/url-resolver';
// Import Material UI icons - Using Outlined variants as default
import SpeedIcon from '@mui/icons-material/SpeedOutlined';
import SecurityIcon from '@mui/icons-material/SecurityOutlined';
import EmojiEmotionsIcon from '@mui/icons-material/EmojiEmotionsOutlined';
import LightbulbIcon from '@mui/icons-material/LightbulbOutlined';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import GroupAddIcon from '@mui/icons-material/GroupAddOutlined';
import ControlCameraIcon from '@mui/icons-material/ControlCameraOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMoreOutlined';
import TuneIcon from '@mui/icons-material/TuneOutlined';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchOutlined';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<
    boolean | null
  >(null);
  const [autoLoggingIn, setAutoLoggingIn] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isQuickStartMode, setIsQuickStartMode] = useState(false);

  // Set mounted state after client-side hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  // Check Quick Start mode after mount (client-side only)
  // SECURITY: Defer computation until after client-side mount to ensure hostname validation
  // During SSR, window is undefined and hostname checks are skipped, which could allow
  // Quick Start mode in cloud deployments if NEXT_PUBLIC_QUICK_START is misconfigured.
  useEffect(() => {
    if (!mounted) return;
    // Dynamic import for client-side only code
    import('@/utils/quick_start').then(({ isQuickStartEnabled }) => {
      setIsQuickStartMode(isQuickStartEnabled());
    });
  }, [mounted]);

  // Auto-login for Quick Start mode
  useEffect(() => {
    if (!mounted) return;
    // Use robust multi-factor detection to determine if Quick Start mode is enabled
    // Dynamic import for client-side only code
    import('@/utils/quick_start').then(({ isQuickStartEnabled }) => {
      const quickStartEnabled = isQuickStartEnabled();

      // Only auto-login if:
      // 1. Quick Start mode is enabled
      // 2. User is not authenticated
      // 3. Not already in the process of logging in
      // 4. No session expiration flag
      if (quickStartEnabled && status === 'unauthenticated' && !autoLoggingIn) {
        const urlParams = new URLSearchParams(window.location.search);
        const isSessionExpired = urlParams.get('session_expired') === 'true';
        const isForcedLogout = urlParams.get('force_logout') === 'true';

        // Don't auto-login if user was forcefully logged out
        if (!isSessionExpired && !isForcedLogout) {
          setAutoLoggingIn(true);

          // Call the local-login endpoint
          fetch(`${getClientApiBaseUrl()}/auth/local-login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          })
            .then(async response => {
              if (response.ok) {
                const data = await response.json();
                // Sign in with NextAuth using the session token
                const { signIn } = await import('next-auth/react');
                await signIn('credentials', {
                  session_token: data.session_token,
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
    // Check if user was redirected due to session expiration or forced logout
    const urlParams = new URLSearchParams(window.location.search);
    const isSessionExpired = urlParams.get('session_expired') === 'true';
    const isForcedLogout = urlParams.get('force_logout') === 'true';

    if (isSessionExpired || isForcedLogout) {
      setSessionExpired(true);
      setBackendSessionValid(false);
      // Clear the parameters from URL
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('session_expired');
      newUrl.searchParams.delete('force_logout');
      window.history.replaceState({}, '', newUrl.toString());

      if (status === 'authenticated') {
        signOut({ redirect: false, callbackUrl: '/' });
      }
      return;
    }

    // Validate backend session immediately when user appears authenticated
    if (
      status === 'authenticated' &&
      session &&
      !sessionExpired &&
      backendSessionValid === null
    ) {
      const validateBackendSession = async () => {
        try {
          const response = await fetch(
            `${getClientApiBaseUrl()}/auth/verify?session_token=${session.session_token}`,
            { headers: { Accept: 'application/json' } }
          );

          if (response.ok) {
            const data = await response.json();
            if (data.authenticated && data.user) {
              setBackendSessionValid(true);
              router.replace('/dashboard');
              return;
            }
          }

          // Backend session invalid - call backend logout to clean up, then frontend logout
          try {
            await fetch(`${getClientApiBaseUrl()}/auth/logout`, {
              method: 'GET',
              headers: { Accept: 'application/json' },
            });
          } catch (logoutError) {}

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

  // Show loading state while NextAuth is loading or while auto-login is in progress
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
      <Grid container component="main" sx={{ height: '100vh' }}>
        {/* Left side - Background and content */}
        <Grid
          sx={{
            backgroundColor: 'primary.dark',
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
          }}
          size={{
            xs: false,
            sm: 4,
            md: 7,
          }}
        >
          <AppBar
            position="relative"
            color="transparent"
            elevation={0}
            sx={{
              background: 'transparent',
              boxShadow: 'none',
            }}
          >
            <Toolbar>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Image
                  src="/logos/rhesis-logo-platypus.png"
                  alt="Rhesis AI Logo"
                  width={200}
                  height={0}
                  style={{ height: 'auto' }}
                  priority
                />
              </Box>
            </Toolbar>
          </AppBar>

          {/* Content overlay on the background - same as unauthenticated view */}
          <Box
            sx={{
              position: 'relative',
              p: { xs: 3, md: 8 },
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              flex: 1,
            }}
          >
            {/* Feature points - same as unauthenticated view */}
            <Box
              sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 3 }}
            >
              <Box>
                <Typography
                  variant="h6"
                  color="common.white"
                  fontWeight="bold"
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
                >
                  <CheckCircleIcon sx={{ color: 'common.white' }} /> Your
                  expertise, in every test.
                </Typography>
                <Typography
                  variant="body2"
                  color="common.white"
                  sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
                >
                  Transform business knowledge and expert input directly into
                  powerful, actionable test cases.
                </Typography>
              </Box>

              <Box>
                <Typography
                  variant="h6"
                  color="common.white"
                  fontWeight="bold"
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
                >
                  <GroupAddIcon sx={{ color: 'common.white' }} /> Collaboration
                  built in.
                </Typography>
                <Typography
                  variant="body2"
                  color="common.white"
                  sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
                >
                  Bring subject matter experts into the loop — seamlessly
                  contribute, review, and refine tests together.
                </Typography>
              </Box>

              <Box>
                <Typography
                  variant="h6"
                  color="common.white"
                  fontWeight="bold"
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
                >
                  <ControlCameraIcon sx={{ color: 'common.white' }} />{' '}
                  End-to-end control.
                </Typography>
                <Typography
                  variant="body2"
                  color="common.white"
                  sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
                >
                  From test generation to execution to results, manage the
                  entire validation process in one place.
                </Typography>
              </Box>

              <Box>
                <Typography
                  variant="h6"
                  color="common.white"
                  fontWeight="bold"
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
                >
                  <TuneIcon sx={{ color: 'common.white' }} /> Scale your
                  validation power.
                </Typography>
                <Typography
                  variant="body2"
                  color="common.white"
                  sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
                >
                  Automate, adapt, and expand test coverage effortlessly — no
                  matter how fast your use cases evolve.
                </Typography>
              </Box>
            </Box>
          </Box>
        </Grid>
        {/* Right side - Authentication message */}
        <Grid
          component={Paper}
          elevation={6}
          square
          size={{
            xs: 12,
            sm: 8,
            md: 5,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: { xs: 3, sm: 6, md: 8 },
            }}
          >
            {/* Show logo on mobile or smaller devices */}
            {isMobile && (
              <Box sx={{ mb: 4 }}>
                <Image
                  src="/logos/rhesis-logo-platypus.png"
                  alt="Rhesis AI Logo"
                  width={160}
                  height={0}
                  style={{ height: 'auto' }}
                  priority
                />
              </Box>
            )}

            <Box
              sx={{
                width: '100%',
                maxWidth: 400,
                textAlign: 'center',
                p: 3,
                borderRadius: theme => theme.shape.borderRadius * 0.5,
                boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
                background: theme =>
                  theme.palette.mode === 'dark'
                    ? 'rgba(0, 0, 0, 0.8)'
                    : 'rgba(255, 255, 255, 0.9)',
              }}
            >
              {isQuickStartMode ? (
                <>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 1,
                      mb: 1,
                    }}
                  >
                    <RocketLaunchIcon
                      sx={{ fontSize: 28, color: 'primary.main' }}
                    />
                    <Typography variant="h5">QUICK START MODE</Typography>
                  </Box>
                  <Typography variant="body1" gutterBottom>
                    Starting with zero configuration. Redirecting to
                    dashboard...
                  </Typography>
                </>
              ) : (
                <>
                  <Typography variant="h5" gutterBottom>
                    Welcome back, {session.user?.name || 'User'}!
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    You&apos;re already logged in. Redirecting you to the
                    dashboard...
                  </Typography>
                </>
              )}
              <CircularProgress sx={{ mt: 2 }} />
            </Box>
          </Box>
        </Grid>
      </Grid>
    );
  }

  return (
    <Grid container component="main" sx={{ height: '100vh' }}>
      {/* Left side - Background and content */}
      <Grid
        sx={{
          backgroundColor: 'primary.dark',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
        size={{
          xs: false,
          sm: 4,
          md: 7,
        }}
      >
        <AppBar
          position="relative"
          color="transparent"
          elevation={0}
          sx={{
            background: 'transparent',
            boxShadow: 'none',
          }}
        >
          <Toolbar>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Image
                src="/logos/rhesis-logo-platypus.png"
                alt="Rhesis AI Logo"
                width={200}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          </Toolbar>
        </AppBar>

        {/* Content overlay on the background */}
        <Box
          sx={{
            position: 'relative',
            p: { xs: 3, md: 8 },
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            flex: 1,
          }}
        >
          {/* Feature points */}
          <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <CheckCircleIcon sx={{ color: 'common.white' }} /> Your
                expertise, in every test.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Transform business knowledge and expert input directly into
                powerful, actionable test cases.
              </Typography>
            </Box>

            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <GroupAddIcon sx={{ color: 'common.white' }} /> Collaboration
                built in.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Bring subject matter experts into the loop — seamlessly
                contribute, review, and refine tests together.
              </Typography>
            </Box>

            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <ControlCameraIcon sx={{ color: 'common.white' }} /> End-to-end
                control.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                From test generation to execution to results, manage the entire
                validation process in one place.
              </Typography>
            </Box>

            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <TuneIcon sx={{ color: 'common.white' }} /> Scale your
                validation power.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Automate, adapt, and expand test coverage effortlessly — no
                matter how fast your use cases evolve.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Grid>
      {/* Right side - Login form */}
      <Grid
        component={Paper}
        elevation={6}
        square
        size={{
          xs: 12,
          sm: 8,
          md: 5,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            p: { xs: 3, sm: 6, md: 8 },
          }}
        >
          {/* Show logo on mobile or smaller devices */}
          {isMobile && (
            <Box sx={{ mb: 4 }}>
              <Image
                src="/logos/rhesis-logo-platypus.png"
                alt="Rhesis AI Logo"
                width={160}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          )}

          <Box sx={{ width: '100%', maxWidth: 400 }}>
            <LoginSection />
          </Box>
        </Box>
      </Grid>
    </Grid>
  );
}
