'use client';

import { Box } from '@mui/material';

const PRIMARY_BLUE = '#50B9E0'; // Intentional: SVG decoration brand color
const LIGHT_BLUE = '#97D5EE'; // Intentional: SVG decoration brand color
const ACCENT_YELLOW = '#FDD803'; // Intentional: SVG decoration brand color
const ACCENT_ORANGE = '#FD6E12'; // Intentional: SVG decoration brand color

export default function BackgroundDecoration() {
  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      <svg
        viewBox="0 0 1440 900"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
        }}
      >
        <path
          d="M-100 300 Q 200 200, 500 350 T 1000 280 T 1600 350"
          fill="none"
          stroke={PRIMARY_BLUE}
          strokeWidth="1.5"
          opacity="0.14"
        />
        <path
          d="M-100 380 Q 300 280, 600 420 T 1100 340 T 1700 420"
          fill="none"
          stroke={LIGHT_BLUE}
          strokeWidth="2"
          opacity="0.16"
        />
        <path
          d="M-100 460 Q 250 360, 550 500 T 1050 400 T 1650 480"
          fill="none"
          stroke={PRIMARY_BLUE}
          strokeWidth="1.5"
          opacity="0.11"
        />

        <circle cx="150" cy="200" r="300" fill="url(#blob1)" opacity="0.6" />
        <circle cx="1300" cy="700" r="250" fill="url(#blob2)" opacity="0.5" />
        <circle cx="700" cy="100" r="200" fill="url(#blob3)" opacity="0.35" />

        <defs>
          <radialGradient id="blob1">
            <stop offset="0%" stopColor={LIGHT_BLUE} stopOpacity="0.18" />
            <stop offset="100%" stopColor={LIGHT_BLUE} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="blob2">
            <stop offset="0%" stopColor={PRIMARY_BLUE} stopOpacity="0.14" />
            <stop offset="100%" stopColor={PRIMARY_BLUE} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="blob3">
            <stop offset="0%" stopColor={ACCENT_YELLOW} stopOpacity="0.12" />
            <stop offset="100%" stopColor={ACCENT_YELLOW} stopOpacity="0" />
          </radialGradient>
        </defs>

        <circle cx="200" cy="500" r="3" fill={PRIMARY_BLUE} opacity="0.25" />
        <circle cx="650" cy="150" r="4" fill={LIGHT_BLUE} opacity="0.3" />
        <circle cx="1100" cy="300" r="3" fill={PRIMARY_BLUE} opacity="0.2" />
        <circle cx="900" cy="750" r="5" fill={ACCENT_YELLOW} opacity="0.25" />
        <circle cx="400" cy="700" r="3" fill={ACCENT_ORANGE} opacity="0.18" />
        <circle cx="1250" cy="500" r="4" fill={LIGHT_BLUE} opacity="0.25" />
      </svg>
    </Box>
  );
}
