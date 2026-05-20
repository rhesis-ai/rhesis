'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Collapse,
  Drawer,
  IconButton,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { BACKDROP_COLORS, BORDER_RADIUS, GREYSCALE } from '@/styles/theme';

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
 * Provides a consistent header ("Filter" + close icon),
 * a scrollable content area, and a sticky footer with Reset/Apply buttons.
 */
export function FilterDrawerShell({
  open,
  onClose,
  onReset,
  onApply,
  title = 'Filter',
  children,
}: FilterDrawerShellProps) {
  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{ keepMounted: true }}
      PaperProps={{
        sx: {
          width: 430,
          display: 'flex',
          flexDirection: 'column',
          p: '30px',
          gap: '30px',
          boxSizing: 'border-box',
        },
      }}
      sx={{
        '& .MuiBackdrop-root': {
          backgroundColor: BACKDROP_COLORS.filter,
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <Typography
          sx={{
            fontSize: 22,
            fontWeight: 700,
            color: GREYSCALE.light.title,
            lineHeight: 1.1,
          }}
        >
          {title}
        </Typography>
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="close"
          sx={{ color: GREYSCALE.light.label }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Content */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '30px',
          pt: '4px',
        }}
      >
        {children}
      </Box>

      {/* Footer */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px',
          flexShrink: 0,
        }}
      >
        <Button
          variant="outlined"
          onClick={onReset}
          sx={{
            borderWidth: 2,
            borderColor: 'primary.main',
            color: 'primary.main',
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
            '&:hover': { borderWidth: 2 },
          }}
        >
          Reset
        </Button>
        <Button
          variant="contained"
          onClick={onApply}
          sx={{
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
          }}
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
  defaultOpen?: boolean;
}

/**
 * Labeled collapsible section within a FilterDrawerShell.
 */
export function FilterSection({
  title,
  children,
  defaultOpen = true,
}: FilterSectionProps) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <Box
      sx={{
        borderTop: `1px solid ${GREYSCALE.light.border}`,
        pt: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setOpen(o => !o)}
      >
        <Typography
          sx={{
            fontSize: 18,
            fontWeight: 700,
            color: GREYSCALE.light.title,
            lineHeight: '25px',
          }}
        >
          {title}
        </Typography>
        {open ? (
          <KeyboardArrowUpIcon
            sx={{ fontSize: 20, color: GREYSCALE.light.label }}
          />
        ) : (
          <KeyboardArrowDownIcon
            sx={{ fontSize: 20, color: GREYSCALE.light.label }}
          />
        )}
      </Box>
      <Collapse in={open}>
        <Box sx={{ pb: '4px' }}>{children}</Box>
      </Collapse>
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
