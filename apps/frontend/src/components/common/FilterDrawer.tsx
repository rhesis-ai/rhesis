'use client';

import * as React from 'react';
import { Box, Button, Drawer, IconButton, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { BACKDROP_COLORS, GREYSCALE } from '@/styles/theme';

// ── FilterDrawerShell ──────────────────────────────────────────────────────────

interface FilterDrawerShellProps {
  open: boolean;
  onClose: () => void;
  onReset: () => void;
  onApply: () => void;
  title?: string;
  children: React.ReactNode;
}

/**
 * Shell for filter side-drawers.
 * Provides a consistent header ("Filters" + close icon),
 * a scrollable content area, and a sticky footer with Reset/Apply buttons.
 */
export function FilterDrawerShell({
  open,
  onClose,
  onReset,
  onApply,
  title = 'Filters',
  children,
}: FilterDrawerShellProps) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: {
          sx: { bgcolor: BACKDROP_COLORS.filter },
        },
      }}
      PaperProps={{
        sx: {
          width: 320,
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 3,
          py: 2,
          borderBottom: `1px solid ${GREYSCALE.light.border}`,
          flexShrink: 0,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          {title}
        </Typography>
        <IconButton size="small" onClick={onClose} aria-label="close">
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 3, py: 2 }}>{children}</Box>

      {/* Footer */}
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          px: 3,
          py: 2,
          borderTop: `1px solid ${GREYSCALE.light.border}`,
          flexShrink: 0,
        }}
      >
        <Button
          variant="outlined"
          fullWidth
          onClick={onReset}
          sx={{
            fontWeight: 700,
            borderWidth: 2,
            '&:hover': { borderWidth: 2 },
          }}
        >
          Reset
        </Button>
        <Button
          variant="contained"
          fullWidth
          onClick={onApply}
          sx={{ fontWeight: 700 }}
        >
          Apply
        </Button>
      </Box>
    </Drawer>
  );
}

// ── FilterSection ──────────────────────────────────────────────────────────────

interface FilterSectionProps {
  title: string;
  children: React.ReactNode;
}

/**
 * Labeled section within a FilterDrawerShell.
 */
export function FilterSection({ title, children }: FilterSectionProps) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography
        sx={{
          fontSize: 12,
          fontWeight: 700,
          lineHeight: '18px',
          color: GREYSCALE.light.subtitle,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          mb: 1.5,
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

// ── filterChipSx ──────────────────────────────────────────────────────────────

/**
 * Returns MUI `sx` styles for a toggle-chip button inside a filter drawer.
 * Pass `true` when the option is currently selected.
 */
export function filterChipSx(active: boolean): object {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    px: '12px',
    py: '6px',
    borderRadius: '999px',
    border: active ? '2px solid' : '1px solid',
    borderColor: active ? 'primary.main' : GREYSCALE.light.border,
    bgcolor: active ? 'primary.main' : 'transparent',
    color: active ? '#fff' : GREYSCALE.light.body,
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    lineHeight: '20px',
    transition: 'all 0.15s ease',
    outline: 'none',
    '&:hover': {
      borderColor: 'primary.main',
      color: active ? '#fff' : 'primary.main',
    },
  };
}
