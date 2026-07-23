'use client';

import React from 'react';
import Box from '@mui/material/Box';
import InputBase from '@mui/material/InputBase';
import SearchIcon from '@mui/icons-material/SearchOutlined';
import { BORDER_RADIUS } from '@/styles/theme';

export interface SearchPillProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  width?: number | string;
  /**
   * `embedded` — toolbar inside a grid card (surface2 on paper bg).
   * `standalone` — directory pages on the page background (needs raised surface).
   */
  variant?: 'embedded' | 'standalone';
}

/**
 * Figma-aligned pill-shaped search field.
 * Gray pill container + InputBase + teal circular search icon (decorative).
 */
export function SearchPill({
  value,
  onChange,
  placeholder = 'Search…',
  width = 288,
  variant = 'embedded',
}: SearchPillProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const isStandalone = variant === 'standalone';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        bgcolor: theme =>
          isStandalone
            ? theme.palette.background.paper
            : theme.palette.greyscale.surface2,
        border: isStandalone ? '1px solid' : 'none',
        borderColor: theme =>
          isStandalone ? theme.palette.greyscale.border : 'transparent',
        borderRadius: '30px', // Intentional: elongated search pill shape
        height: 38,
        pl: '16px',
        pr: '4px',
        width,
        flexShrink: 0,
      }}
    >
      <InputBase
        inputRef={inputRef}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        sx={{
          flex: 1,
          fontSize: 14,
          color: theme => theme.palette.greyscale.body,
          '& input::placeholder': {
            color: theme =>
              isStandalone
                ? theme.palette.greyscale.subtitle
                : theme.palette.greyscale.border,
            opacity: 1,
          },
        }}
      />
      {/* Decorative icon button — clicking focuses the input */}
      <Box
        component="button"
        type="button"
        aria-hidden
        tabIndex={-1}
        onClick={() => inputRef.current?.focus()}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          borderRadius: BORDER_RADIUS.pill,
          border: 'none',
          p: '9px',
          width: 30,
          height: 30,
          flexShrink: 0,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'primary.dark' },
        }}
      >
        <SearchIcon sx={{ fontSize: 18 }} />
      </Box>
    </Box>
  );
}

export default SearchPill;
