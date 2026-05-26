'use client';

import React from 'react';
import Box from '@mui/material/Box';
import InputBase from '@mui/material/InputBase';
import IconButton from '@mui/material/IconButton';
import SearchIcon from '@mui/icons-material/SearchOutlined';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

export interface SearchPillProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  width?: number | string;
}

/**
 * Figma-aligned pill-shaped search field.
 * Gray pill container + InputBase + teal circular search button.
 */
export function SearchPill({
  value,
  onChange,
  placeholder = 'Search…',
  width = 288,
}: SearchPillProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        bgcolor: theme =>
          theme.palette.mode === 'light'
            ? GREYSCALE.light.surface2
            : theme.palette.action.hover,
        borderRadius: '30px', // Intentional: elongated search pill shape
        height: 38,
        pl: '16px',
        pr: '4px',
        width,
        flexShrink: 0,
      }}
    >
      <InputBase
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        sx={{
          flex: 1,
          fontSize: 14,
          '& input::placeholder': {
            color: GREYSCALE.light.border,
            opacity: 1,
          },
        }}
      />
      <IconButton
        aria-label="Search"
        sx={{
          bgcolor: 'primary.main',
          color: '#fff',
          borderRadius: BORDER_RADIUS.pill,
          p: '9px',
          width: 30,
          height: 30,
          flexShrink: 0,
          '&:hover': { bgcolor: 'primary.dark' },
          '& .MuiSvgIcon-root': { fontSize: 18 },
        }}
      >
        <SearchIcon />
      </IconButton>
    </Box>
  );
}

export default SearchPill;
