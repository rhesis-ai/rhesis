'use client';

import * as React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import Image from 'next/image';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
import BackgroundDecoration from '../components/auth/BackgroundDecoration';
import { getClientApiBaseUrl } from '../utils/url-resolver';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchOutlined';

const MUTED_TEXT = '#6B7280'; // Intentional: landing page muted text
const FEATURE_TEXT = '#374151'; // Intentional: landing page feature text
const CARD_BORDER = '#E5E7EB'; // Intentional: landing page card border
const FOOTER_TEXT = '#9CA3AF'; // Intentional: landing page footer text
const BADGE_BG = '#EBF7FC'; // Intentional: landing page badge background
const BADGE_BORDER = 'rgba(80,185,224,0.15)'; // Intentional: landing page badge border
const GRADIENT_END = '#3a9ec5'; // Intentional: landing page gradient end color
const BRAND_BLUE = '#50B9E0'; // Intentional: brand color for SVG elements

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
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
        position: 'relative',
        overflowX: 'hidden',
      }}
    >
      <BackgroundDecoration />

      {/* Top navigation */}
      <Box
        component="nav"
        sx={{
          position: 'relative',
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: { xs: 2.5, md: 5 },
          py: 2.5,
        }}
      >
        <Box
          component="a"
          href="https://www.rhesis.ai"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            textDecoration: 'none',
          }}
        >
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: '12px', // Intentional: logo border radius
              overflow: 'hidden',
              flexShrink: 0,
            }}
          >
            <Image
              src="/logos/rhesis-logo-favicon.svg"
              alt="Rhesis AI"
              width={44}
              height={44}
              priority
            />
          </Box>
          <Typography
            sx={{
              fontSize: 22,
              fontWeight: 700,
              color: 'secondary.dark',
              letterSpacing: '-0.03em',
              fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
            }}
          >
            Rhesis AI
          </Typography>
        </Box>

        <Box
          sx={{
            display: { xs: 'none', md: 'flex' },
            alignItems: 'center',
            gap: 3,
          }}
        >
          {[
            { label: 'Documentation', href: 'https://docs.rhesis.ai' },
            { label: 'Blog', href: 'https://rhesis.ai/blog' },
          ].map(link => (
            <Typography
              key={link.label}
              component="a"
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                fontSize: 14,
                fontWeight: 500,
                color: MUTED_TEXT,
                textDecoration: 'none',
                transition: 'color 0.15s',
                '&:hover': { color: 'secondary.dark' },
              }}
            >
              {link.label}
            </Typography>
          ))}
        </Box>
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          position: 'relative',
          zIndex: 10,
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: { xs: 2, md: 3 },
          py: { xs: 3, md: 2 },
          pb: { xs: 5, md: 7.5 },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: { xs: 6, md: 10 },
            maxWidth: 1100,
            width: '100%',
            flexDirection: { xs: 'column', md: 'row' },
          }}
        >
          {/* Left — hero copy */}
          <Box
            sx={{
              flex: '1 1 50%',
              maxWidth: 480,
              textAlign: { xs: 'center', md: 'left' },
            }}
          >
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 1,
                px: 1.75,
                py: 0.75,
                borderRadius: '100px', // Intentional: pill badge shape
                bgcolor: BADGE_BG,
                color: 'primary.main',
                fontSize: 13,
                fontWeight: 600,
                mb: 3.5,
                border: `1px solid ${BADGE_BORDER}`,
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke={BRAND_BLUE}
                strokeWidth="2.5"
              >
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              Full Testing Lifecycle
            </Box>

            <Typography
              sx={{
                fontSize: { xs: 30, sm: 38, md: 48 },
                fontWeight: 800,
                lineHeight: 1.1,
                color: 'secondary.dark',
                letterSpacing: '-0.04em',
                mb: 2.5,
                fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
              }}
            >
              The testing platform{' '}
              <Box
                component="br"
                sx={{ display: { xs: 'none', md: 'block' } }}
              />
              for{' '}
              <Box
                component="span"
                sx={{
                  background: `linear-gradient(135deg, ${BRAND_BLUE} 0%, ${GRADIENT_END} 100%)`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                AI teams.
              </Box>
            </Typography>

            <Typography
              sx={{
                fontSize: { xs: 16, md: 18 },
                lineHeight: 1.6,
                color: MUTED_TEXT,
                mb: 5.5,
                maxWidth: 420,
                mx: { xs: 'auto', md: 0 },
              }}
            >
              Bring engineers, PMs, and domain experts together to generate
              tests, simulate (adversarial) conversations, and trace every
              failure to its root cause.
            </Typography>

            <Box
              sx={{
                display: { xs: 'none', sm: 'flex' },
                flexDirection: 'column',
                gap: 2,
                alignItems: { xs: 'center', md: 'flex-start' },
              }}
            >
              {[
                {
                  color: 'primary.main',
                  text: 'Conversation simulation & red-teaming',
                },
                {
                  color: 'secondary.light',
                  text: 'Collaborative test curation',
                },
                {
                  color: 'secondary.main',
                  text: 'Traces, reviews & monitoring',
                },
              ].map(feature => (
                <Box
                  key={feature.text}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.75,
                  }}
                >
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%', // Intentional: circular dot
                      bgcolor: feature.color,
                      flexShrink: 0,
                    }}
                  />
                  <Typography
                    sx={{
                      fontSize: 15,
                      fontWeight: 500,
                      color: FEATURE_TEXT,
                    }}
                  >
                    {feature.text}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>

          {/* Right — auth card */}
          <Box
            sx={{
              flex: '0 0 auto',
              width: { xs: '100%', sm: 420 },
              maxWidth: 420,
              bgcolor: 'background.default',
              border: `1px solid ${CARD_BORDER}`,
              borderRadius: { xs: '16px', sm: '20px' }, // Intentional: auth card radius
              p: { xs: '32px 24px', sm: '44px 40px' },
              boxShadow:
                '0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06), 0 24px 48px rgba(0,0,0,0.04)',
            }}
          >
            <LoginSection />
          </Box>
        </Box>
      </Box>

      {/* Footer */}
      <Box
        component="footer"
        sx={{
          position: 'relative',
          zIndex: 10,
          textAlign: 'center',
          py: 2.5,
          fontSize: 12,
          color: FOOTER_TEXT,
        }}
      >
        © 2026 Rhesis AI
      </Box>
    </Box>
  );
}
