'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  Button,
  Stack,
  CircularProgress,
} from '@mui/material';
import { BACKDROP_COLORS } from '@/styles/theme';
import {
  drawerFooterCancelButtonSx,
  drawerFooterDeleteButtonSx,
  drawerFooterSaveButtonSx,
  DRAWER_WIDTH,
} from '@/components/common/drawerFormFieldSx';
import { rem } from '@/styles/theme-constants';

export interface BaseDrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  titleIcon?: React.ReactNode;
  children: React.ReactNode;
  loading?: boolean;
  onSave?: () => void;
  /** Disable the save button (button remains visible) */
  saveDisabled?: boolean;
  /** A plain string renders as the usual red error line. Pass a node (e.g.
   * `<QuotaNotice>`) for a gate that isn't a failure -- `approaching` and
   * `pastIncluded` zones aren't errors and shouldn't render in error red. */
  error?: React.ReactNode;
  /** Id for a string `error`, so the field it's about can point at it. */
  errorId?: string;
  saveButtonText?: string;
  /** Optional data-tour attribute for onboarding (save button). */
  saveDataTour?: string;
  closeButtonText?: string;
  /** Shows a Back button before the save button, for multi-step drawers. */
  onBack?: () => void;
  onDelete?: () => void;
  deleteButtonText?: string;
  deleteDisabled?: boolean;
  width?: number | string;
  showHeader?: boolean;
  anchor?: 'left' | 'right';
  /** `form` — scrollable stacked sections; `fill` — full-height workspace (traces, test results). */
  contentLayout?: 'form' | 'fill';
  /** Drops the paper's padding and gap, for a fill workspace that draws its own chrome. */
  disablePadding?: boolean;
}

// Utility function to filter out duplicates and invalid entries
export function filterUniqueValidOptions<
  T extends { id: string | number; name: string },
>(options: T[]): T[] {
  // First, filter out entries with empty or invalid names
  const validOptions = options.filter(
    option =>
      option &&
      option.name &&
      typeof option.name === 'string' &&
      option.name.trim() !== ''
  );

  // Then remove duplicates based on both id and name
  const seen = new Set();
  return validOptions.filter(option => {
    const key = `${option.id}-${option.name}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export default function BaseDrawer({
  open,
  onClose,
  title,
  titleIcon,
  children,
  loading = false,
  onSave,
  saveDisabled = false,
  error,
  errorId,
  saveButtonText = 'Save Changes',
  saveDataTour,
  closeButtonText = 'Cancel',
  onBack,
  onDelete,
  deleteButtonText = 'Delete',
  deleteDisabled = false,
  width = DRAWER_WIDTH,
  showHeader = true,
  anchor = 'right',
  contentLayout = 'form',
  disablePadding = false,
}: BaseDrawerProps) {
  const hasFooter = !!(closeButtonText || onSave || onDelete || error);
  const isFillLayout = contentLayout === 'fill';
  const paperRef = React.useRef<HTMLDivElement>(null);

  // A failed save marks fields invalid but leaves focus on the button, so a
  // screen reader user hears nothing. Move focus to the first invalid field,
  // where its label and error are read (WCAG 3.3.1).
  const handleSave = onSave
    ? () => {
        onSave();
        window.setTimeout(() => {
          paperRef.current
            ?.querySelector<HTMLElement>('[aria-invalid="true"]')
            ?.focus();
        }, 0);
      }
    : undefined;

  return (
    <Drawer
      anchor={anchor}
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{ keepMounted: true }}
      PaperProps={{
        ref: paperRef,
        sx: {
          // Full width on narrow viewports so the form reflows (WCAG 1.4.10).
          width: { xs: '100%', sm: width },
          maxWidth: '100%',
          display: 'flex',
          flexDirection: 'column',
          p: disablePadding ? 0 : { xs: 2, sm: '30px' },
          gap: disablePadding ? 0 : { xs: 3, sm: '40px' },
          boxSizing: 'border-box',
        },
      }}
      sx={{
        '& .MuiBackdrop-root': {
          backgroundColor: BACKDROP_COLORS.create,
        },
      }}
    >
      {/* Title row — no border, no close button */}
      {showHeader && (
        <Box sx={{ flexShrink: 0 }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {titleIcon}
            <Typography
              sx={{
                fontSize: rem(23),
                fontWeight: 700,
                lineHeight: rem(27.6),
                color: theme => theme.palette.greyscale.title,
              }}
            >
              {title}
            </Typography>
          </Stack>
        </Box>
      )}

      {/* Form content — scrollable, 40px gap between child rows.
          pt: '10px' gives room for MUI floating labels (which translate -9px up)
          so they aren't clipped by the overflowY container. */}
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: isFillLayout ? 'hidden' : 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: isFillLayout ? 0 : '40px',
          pt: isFillLayout ? 0 : '10px',
        }}
      >
        {children}
      </Box>

      {/* Bottom toolbar — only rendered when there is something to show */}
      {hasFooter && (
        <Box sx={{ flexShrink: 0 }}>
          {error &&
            (typeof error === 'string' ? (
              <Typography
                id={errorId}
                role="alert"
                color="error"
                variant="body2"
                sx={{ mb: 1.5 }}
              >
                {error}
              </Typography>
            ) : (
              <Box role="alert" sx={{ mb: 1.5 }}>
                {error}
              </Box>
            ))}
          <Box
            sx={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}
          >
            {closeButtonText && (
              <Button
                variant="outlined"
                onClick={onClose}
                disabled={loading}
                sx={drawerFooterCancelButtonSx}
              >
                {closeButtonText}
              </Button>
            )}
            {onDelete && (
              <Button
                variant="outlined"
                color="error"
                onClick={onDelete}
                disabled={loading || deleteDisabled}
                sx={drawerFooterDeleteButtonSx}
              >
                {deleteButtonText}
              </Button>
            )}
            {onBack && (
              <Button
                variant="outlined"
                onClick={onBack}
                disabled={loading}
                sx={drawerFooterCancelButtonSx}
              >
                Back
              </Button>
            )}
            {onSave && (
              <Button
                variant="contained"
                onClick={handleSave}
                disabled={loading || saveDisabled}
                {...(saveDataTour ? { 'data-tour': saveDataTour } : {})}
                startIcon={
                  loading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : undefined
                }
                sx={drawerFooterSaveButtonSx}
              >
                {loading ? 'Executing...' : saveButtonText}
              </Button>
            )}
          </Box>
        </Box>
      )}
    </Drawer>
  );
}
