'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import Image from 'next/image';
import BackgroundDecoration from './BackgroundDecoration';
import { lightTheme } from '@/styles/theme';

const MUTED_TEXT = '#6B7280'; // Intentional: landing page muted text
const FEATURE_TEXT = '#374151'; // Intentional: landing page feature text
const CARD_BORDER = '#E5E7EB'; // Intentional: landing page card border
const FOOTER_TEXT = '#9CA3AF'; // Intentional: landing page footer text
const BADGE_BG = '#EBF7FC'; // Intentional: landing page badge background
const BADGE_BORDER = 'rgba(80,185,224,0.15)'; // Intentional: landing page badge border
const GRADIENT_END = '#3a9ec5'; // Intentional: landing page gradient end color
const BRAND_BLUE = '#50B9E0'; // Intentional: brand color for SVG elements

interface AuthPageShellProps {
  children: React.ReactNode;
}

export default function AuthPageShell({ children }: AuthPageShellProps) {
  return (
    <ThemeProvider theme={lightTheme}>
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
            target="_blank"
            rel="noopener noreferrer"
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
              gap: { xs: 6, md: 16, lg: 20, xl: 24 },
              maxWidth: 1100,
              width: '100%',
              flexDirection: { xs: 'column', md: 'row' },
            }}
          >
            {/* Left — hero copy */}
            <Box
              sx={{
                flex: 1,
                maxWidth: 560,
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
                  aria-hidden="true"
                  focusable="false"
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
              {children}
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
    </ThemeProvider>
  );
}
