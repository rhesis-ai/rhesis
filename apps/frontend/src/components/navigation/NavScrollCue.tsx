'use client';

import React from 'react';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import { BORDER_RADIUS } from '@/styles/theme';

const CUE_HEIGHT_SPACING = 4.25;

interface NavScrollCueProps {
  direction: 'up' | 'down';
  visible: boolean;
  onClick: () => void;
}

/**
 * Fade plus a small arrow over the top or bottom edge of the scrolling nav,
 * shown while there is more nav that way. The scrollbar is hidden, so this is
 * the only sign the nav scrolls.
 */
export function NavScrollCue({
  direction,
  visible,
  onClick,
}: NavScrollCueProps) {
  const down = direction === 'down';
  return (
    <Box
      aria-hidden={!visible}
      sx={{
        position: 'absolute',
        left: 0,
        right: 0,
        [down ? 'bottom' : 'top']: 0,
        height: theme => theme.spacing(CUE_HEIGHT_SPACING),
        display: 'flex',
        justifyContent: 'center',
        alignItems: down ? 'flex-end' : 'flex-start',
        background: theme =>
          `linear-gradient(to ${down ? 'bottom' : 'top'}, transparent, ${theme.palette.greyscale.surface1} 70%)`,
        opacity: visible ? 1 : 0,
        transition: 'opacity 0.18s ease',
        // The fade itself must not block clicks on the nav items under it.
        pointerEvents: 'none',
        zIndex: 1,
        '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
      }}
    >
      <ButtonBase
        onClick={onClick}
        tabIndex={visible ? 0 : -1}
        aria-label={down ? 'Scroll navigation down' : 'Scroll navigation up'}
        sx={{
          pointerEvents: visible ? 'auto' : 'none',
          px: 1.25,
          borderRadius: BORDER_RADIUS.sm,
          color: theme => theme.palette.greyscale.subtitle,
          '&:hover': {
            bgcolor: theme => theme.palette.greyscale.surface2,
            color: theme => theme.palette.greyscale.label,
          },
        }}
      >
        {down ? (
          <ArrowDropDownIcon
            fontSize="small"
            sx={{
              // A short nudge when it appears draws the eye once, then stops.
              ...(visible && {
                animation: 'navScrollCueNudge 1.6s ease-in-out 2',
              }),
              '@keyframes navScrollCueNudge': {
                '50%': { transform: 'translateY(2px)' },
              },
              '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
            }}
          />
        ) : (
          <ArrowDropUpIcon fontSize="small" />
        )}
      </ButtonBase>
    </Box>
  );
}

export default NavScrollCue;
