'use client';

import { Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';

/**
 * The backdrop behind the auth pages, matching the rhesis.ai hero.
 *
 * Light uses the site's `hero-bg` wash, masked so its natural bottom edge
 * never shows as a seam. Dark can't reuse it — the wash is painted for a white
 * canvas and turns into a milky sheet over a near-black one, which eats the
 * headline. Dark gets the site's aurora instead: brand blooms blended with
 * `screen` over black, so type stays at full contrast.
 */

/** Matches `DarkAuroraGlow` variant="hero" on the website. */
const AURORA_LAYERS = [
  'radial-gradient(58% 48% at 34% 26%, rgba(0,158,215,0.52) 0%, rgba(0,104,148,0.20) 44%, transparent 74%)',
  'radial-gradient(42% 38% at 86% 58%, rgba(255,206,0,0.12) 0%, transparent 68%)',
  'radial-gradient(50% 42% at 10% 70%, rgba(56,132,255,0.16) 0%, transparent 70%)',
].join(', ');

const WASH_FADE =
  'linear-gradient(to bottom, #000 0%, #000 48%, transparent 94%)';
const AURORA_FADE =
  'linear-gradient(to bottom, #000 0%, #000 56%, transparent 98%)';

export default function BackgroundDecoration() {
  const isDark = useTheme().palette.mode === 'dark';
  const fade = isDark ? AURORA_FADE : WASH_FADE;

  return (
    <Box
      aria-hidden="true"
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        maskImage: fade,
        WebkitMaskImage: fade,
      }}
    >
      {isDark ? (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            backgroundImage: AURORA_LAYERS,
            filter: 'blur(10px)',
            mixBlendMode: 'screen',
          }}
        />
      ) : (
        <Box
          component="img"
          src="/auth/hero-wash.png"
          alt=""
          sx={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            objectPosition: 'center 22%',
            userSelect: 'none',
          }}
        />
      )}
    </Box>
  );
}
