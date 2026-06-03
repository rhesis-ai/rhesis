'use client';

import * as React from 'react';

// ── useFilterDrawerDraft ───────────────────────────────────────────────────────

/**
 * Manages the "draft" filter state that lives inside a filter drawer.
 *
 * Behaviour:
 * - Draft is reset to `committed` whenever the drawer opens.
 * - `handleReset` resets draft to `empty` (matches the "Reset" button).
 * - `handleApply` commits the draft via `onApply` then closes the drawer.
 */
export function useFilterDrawerDraft<T>(
  open: boolean,
  committed: T,
  empty: T,
  onApply: (filters: T) => void,
  onClose: () => void
): {
  draft: T;
  setDraft: React.Dispatch<React.SetStateAction<T>>;
  handleReset: () => void;
  handleApply: () => void;
} {
  const [draft, setDraft] = React.useState<T>(committed);

  React.useEffect(() => {
    if (open) setDraft(committed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleReset = React.useCallback(() => setDraft(empty), [empty]);

  const handleApply = React.useCallback(() => {
    onApply(draft);
    onClose();
  }, [draft, onApply, onClose]);

  return { draft, setDraft, handleReset, handleApply };
}
import {
  Box,
  Button,
  ButtonBase,
  Collapse,
  Drawer,
  IconButton,
  Typography,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { BACKDROP_COLORS, BORDER_RADIUS } from '@/styles/theme';

// ── FilterDrawerShell ──────────────────────────────────────────────────────────

interface FilterDrawerShellProps {
  open: boolean;
  onClose: () => void;
  /** Omit to hide the Reset button. */
  onReset?: () => void;
  /** Label for the reset button. Defaults to "Reset". */
  resetLabel?: string;
  /** Omit to hide the Apply button (e.g. when selection has immediate effect). */
  onApply?: () => void;
  title?: string;
  children: React.ReactNode;
}

/**
 * Shell for filter side-drawers.
 * Provides a consistent header ("Filter" + close icon),
 * a scrollable content area, and a sticky footer with Reset/Apply buttons.
 * Pass `onApply` to show the Apply button; omit it when selection has immediate effect.
 */
export function FilterDrawerShell({
  open,
  onClose,
  onReset,
  resetLabel = 'Reset',
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
          p: 3.75,
          gap: 3.75,
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
            color: theme => theme.palette.greyscale.title,
            lineHeight: 1.1,
          }}
        >
          {title}
        </Typography>
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="close"
          sx={{ color: theme => theme.palette.greyscale.label }}
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
          gap: 3.75,
          pt: '4px',
        }}
      >
        {children}
      </Box>

      {/* Footer — hidden when neither button is needed */}
      {(onReset || onApply) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
            flexShrink: 0,
          }}
        >
          {onReset && (
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
              {resetLabel}
            </Button>
          )}
          {onApply && (
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
          )}
        </Box>
      )}
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
        borderTop: theme => `1px solid ${theme.palette.greyscale.border}`,
        pt: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <ButtonBase
        onClick={() => setOpen(o => !o)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          userSelect: 'none',
        }}
      >
        <Typography
          sx={{
            fontSize: 18,
            fontWeight: 700,
            color: theme => theme.palette.greyscale.title,
            lineHeight: '25px',
          }}
        >
          {title}
        </Typography>
        {open ? (
          <KeyboardArrowUpIcon
            sx={{ fontSize: 20, color: theme => theme.palette.greyscale.label }}
          />
        ) : (
          <KeyboardArrowDownIcon
            sx={{ fontSize: 20, color: theme => theme.palette.greyscale.label }}
          />
        )}
      </ButtonBase>
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
export function filterChipSx(active: boolean): SxProps<Theme> {
  return theme => ({
    display: 'inline-flex',
    alignItems: 'center',
    px: '12px',
    py: '6px',
    borderRadius: '999px',
    border: active ? '2px solid' : '1px solid',
    borderColor: active ? 'primary.main' : theme.palette.greyscale.border,
    bgcolor: active ? 'primary.main' : 'transparent',
    color: active
      ? theme.palette.primary.contrastText
      : theme.palette.greyscale.body,
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    lineHeight: '20px',
    transition: 'all 0.15s ease',
    outline: 'none',
    '&:hover': {
      borderColor: 'primary.main',
      color: active ? theme.palette.primary.contrastText : 'primary.main',
    },
  });
}
