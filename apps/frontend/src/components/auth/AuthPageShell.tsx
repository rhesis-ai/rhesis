'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import BrandMark from '@/components/common/BrandMark';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import BackgroundDecoration from './BackgroundDecoration';
import {
  AUTH_FONT_DISPLAY,
  AUTH_FONT_MONO,
  AUTH_FONT_SANS,
  AUTH_SHAPE,
  getAuthTokens,
} from './authTokens';
import { scaledVh } from '@/styles/viewport-scaling';

/**
 * The frame around every auth page: nav, message column, auth card, footer.
 *
 * Copy in the message column is the rhesis.ai homepage hero, verbatim, so the
 * two pages read as one product. Update it when the site's hero changes rather
 * than writing a sign-in-specific variant that drifts.
 *
 * The shell deliberately does *not* wrap its children in a fixed theme — it
 * follows the app's `ThemeContextProvider`, which falls back to the browser's
 * `prefers-color-scheme` when the visitor has no stored preference. That is the
 * normal case here, since nobody is signed in yet.
 */

const NAV_LINKS = [
  { label: 'Documentation', href: 'https://docs.rhesis.ai' },
  { label: 'Blog', href: 'https://rhesis.ai/blog' },
];

const EYEBROW = 'Collaborative platform for continuous AI improvement';

const BENEFITS = [
  'Expert knowledge becomes test coverage.',
  'Every version measured against the same bar.',
  'Made and hosted in Europe.',
];

const BADGES = ['Open Source', 'Public Preview', 'use it via UI, SDK, MCP'];

const GITHUB_URL = 'https://github.com/rhesis-ai/rhesis';

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="m4 12.5 5 5L20 6.5" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M12 .5C5.7.5.5 5.7.5 12c0 5.1 3.3 9.4 7.9 10.9.6.1.8-.2.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.7 1.3 3.4 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.8 0-1.3.5-2.3 1.2-3.2-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.9 1.2 1.9 1.2 3.2 0 4.5-2.7 5.5-5.3 5.8.4.4.8 1.1.8 2.2v3.3c0 .4.2.7.8.6 4.6-1.5 7.9-5.8 7.9-10.9C23.5 5.7 18.3.5 12 .5Z" />
    </svg>
  );
}

interface AuthPageShellProps {
  children: React.ReactNode;
}

export default function AuthPageShell({ children }: AuthPageShellProps) {
  const { mode, brandColor } = useTheme().palette;
  const t = getAuthTokens(mode, brandColor);
  // `NavigationProvider` wraps every route, auth pages included, so the
  // server-resolved branding is available here without a second env read.
  const { branding } = useNavigationItems();
  const productName = branding?.productName ?? 'Rhesis AI';
  const isRebranded = productName !== 'Rhesis AI';
  // A rebranded sign-in page must not send its users to rhesis.ai, and there is
  // no configured homepage to send them to instead — so the wordmark stops
  // being a link and just labels the page.
  const wordmarkHref = isRebranded ? undefined : 'https://www.rhesis.ai';

  return (
    <Box
      sx={{
        minHeight: scaledVh(),
        display: 'flex',
        flexDirection: 'column',
        bgcolor: t.ground,
        color: t.body,
        fontFamily: AUTH_FONT_SANS,
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
          px: { xs: 2.5, md: 5.5 },
          py: 2.25,
        }}
      >
        <Box
          {...(wordmarkHref
            ? {
                component: 'a' as const,
                href: wordmarkHref,
                target: '_blank',
                rel: 'noopener noreferrer',
              }
            : {})}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            textDecoration: 'none',
          }}
        >
          <BrandMark
            src={branding?.iconUrl}
            size={44}
            alt={productName}
            priority
          />
          <Typography
            sx={{
              fontFamily: AUTH_FONT_DISPLAY,
              fontSize: 20,
              fontWeight: 800,
              letterSpacing: '-0.01em',
              color: mode === 'dark' ? '#fff' : '#111827',
            }}
          >
            {productName}
          </Typography>
        </Box>

        <Box
          sx={{
            display: { xs: 'none', md: 'flex' },
            alignItems: 'center',
            gap: 3.25,
          }}
        >
          {NAV_LINKS.map(link => (
            <Typography
              key={link.label}
              component="a"
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                fontSize: 14,
                fontWeight: 500,
                color: t.muted,
                textDecoration: 'none',
                transition: 'color 0.15s',
                '&:hover': { color: t.ink },
              }}
            >
              {link.label}
            </Typography>
          ))}
          <Box
            component="a"
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.875,
              height: 34,
              px: 1.5,
              borderRadius: AUTH_SHAPE.button,
              bgcolor: t.chip,
              color: mode === 'dark' ? '#e5e7eb' : '#2c2c2c',
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'opacity 0.15s',
              '&:hover': { opacity: 0.8 },
            }}
          >
            <GitHubIcon />
            GitHub
          </Box>
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
          px: { xs: 2, md: 5.5 },
          py: { xs: 3, md: 2 },
          pb: { xs: 5, md: 3 },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: { xs: 5, md: 10, lg: 12 },
            maxWidth: 1080,
            width: '100%',
            flexDirection: { xs: 'column', md: 'row' },
          }}
        >
          {/* Left — message column, mirroring the rhesis.ai hero */}
          <Box
            sx={{
              flex: 1,
              maxWidth: 520,
              display: 'flex',
              flexDirection: 'column',
              alignItems: { xs: 'center', md: 'flex-start' },
              textAlign: { xs: 'center', md: 'left' },
              gap: 3.25,
            }}
          >
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: 28,
                px: 2.25,
                py: 0.5,
                borderRadius: AUTH_SHAPE.pill,
                border: `1px solid ${t.hairline}`,
                bgcolor: t.pill,
                boxShadow:
                  mode === 'dark' ? 'none' : '0 2px 20px 0 rgba(21,21,22,0.07)',
                fontSize: 12,
                fontWeight: 300,
                textTransform: 'uppercase',
                letterSpacing: '0.6px',
                color: t.ink,
              }}
            >
              {EYEBROW}
            </Box>

            <Typography
              component="h1"
              sx={{
                fontSize: { xs: 32, sm: 40, md: 46 },
                fontWeight: 700,
                lineHeight: 1.02,
                letterSpacing: '-0.03em',
                color: t.ink,
                textWrap: 'balance',
              }}
            >
              Get the{' '}
              <Box component="span" sx={{ fontWeight: 300, color: t.accent }}>
                knowledge
              </Box>{' '}
              you need{' '}
              <Box component="span" sx={{ fontWeight: 300, color: t.accent }}>
                to improve
              </Box>{' '}
              your agents.
            </Typography>

            <Typography
              sx={{
                fontSize: { xs: 16, md: 18 },
                lineHeight: 1.45,
                color: t.body,
                maxWidth: '34ch',
              }}
            >
              A shared workspace where domain experts annotate behavior and
              engineers get the feedback they need to improve the agent.
            </Typography>

            <Box
              component="ul"
              sx={{
                display: { xs: 'none', sm: 'flex' },
                flexDirection: 'column',
                gap: 1.625,
                m: 0,
                p: 0,
                listStyle: 'none',
              }}
            >
              {BENEFITS.map(benefit => (
                <Box
                  key={benefit}
                  component="li"
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.375,
                    fontSize: 15.5,
                    fontWeight: 500,
                    color: t.ink,
                  }}
                >
                  <Box sx={{ display: 'flex', color: t.accent }}>
                    <CheckIcon />
                  </Box>
                  {benefit}
                </Box>
              ))}
            </Box>

            <Box
              sx={{
                display: { xs: 'none', sm: 'flex' },
                flexWrap: 'wrap',
                gap: 1.25,
                justifyContent: { xs: 'center', md: 'flex-start' },
              }}
            >
              {BADGES.map(badge => (
                <Box
                  key={badge}
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    px: 1.5,
                    py: 0.75,
                    borderRadius: AUTH_SHAPE.button,
                    border: `1px solid ${t.hairline}`,
                    bgcolor: t.badge,
                    fontFamily: AUTH_FONT_MONO,
                    fontSize: 11,
                    color: t.muted,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {badge}
                </Box>
              ))}
            </Box>
          </Box>

          {/* Right — auth card */}
          <Box
            sx={{
              flex: '0 0 auto',
              width: { xs: '100%', sm: 404 },
              maxWidth: 404,
              bgcolor: t.surface,
              border: `1px solid ${t.hairline}`,
              borderRadius: AUTH_SHAPE.card,
              p: { xs: '28px 22px', sm: '34px 32px' },
              boxShadow: t.cardShadow,
              backdropFilter: 'blur(6px)',
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
          py: 2.25,
          fontSize: 12,
          color: t.muted,
        }}
      >
        © 2026 {productName}
      </Box>
    </Box>
  );
}
