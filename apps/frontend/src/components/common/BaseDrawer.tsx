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
  error?: string;
  saveButtonText?: string;
  /** Optional data-tour attribute for onboarding (save button). */
  saveDataTour?: string;
  closeButtonText?: string;
  onDelete?: () => void;
  deleteButtonText?: string;
  deleteDisabled?: boolean;
  width?: number | string;
  showHeader?: boolean;
  anchor?: 'left' | 'right';
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
  saveButtonText = 'Save Changes',
  saveDataTour,
  closeButtonText = 'Cancel',
  onDelete,
  deleteButtonText = 'Delete',
  deleteDisabled = false,
  width = DRAWER_WIDTH,
  showHeader = true,
  anchor = 'right',
}: BaseDrawerProps) {
  const hasFooter = !!(closeButtonText || onSave || onDelete || error);

  return (
    <Drawer
      anchor={anchor}
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{ keepMounted: true }}
      PaperProps={{
        sx: {
          width: width,
          display: 'flex',
          flexDirection: 'column',
          p: '30px',
          gap: '40px',
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
                fontSize: 23,
                fontWeight: 700,
                lineHeight: '27.6px',
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
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '40px',
          pt: '10px',
        }}
      >
        {children}
      </Box>

      {/* Bottom toolbar — only rendered when there is something to show */}
      {hasFooter && (
        <Box sx={{ flexShrink: 0 }}>
          {error && (
            <Typography color="error" variant="body2" sx={{ mb: 1.5 }}>
              {error}
            </Typography>
          )}
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
            {onSave && (
              <Button
                variant="contained"
                onClick={onSave}
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
