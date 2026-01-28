'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  Button,
  Stack,
  CircularProgress,
  // Divider // Keep or remove based on whether header/footer have borders
} from '@mui/material';

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
  closeButtonText?: string;
  width?: number | string;
  showHeader?: boolean;
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
  closeButtonText = 'Cancel',
  width = 600,
  showHeader = true,
}: BaseDrawerProps) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{
        keepMounted: true, // Or false, depending on preference
        slotProps: {
          backdrop: {
            sx: {
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      }}
      slotProps={{
        backdrop: {
          sx: {
            // Ensure backdrop is below drawer paper but above other content if necessary
            zIndex: theme => theme.zIndex.drawer - 1,
          },
        },
      }}
      PaperProps={{
        sx: {
          width: width,
          zIndex: theme => theme.zIndex.drawer + 1, // Ensure Paper is above AppBar and its own backdrop
          display: 'flex', // Added for flex structure if header/content/footer are direct children of Paper
          flexDirection: 'column',
          justifyContent: 'space-between', // If header/content/footer structure is used
        },
      }}
      sx={{
        // Sx for the Drawer root
        zIndex: theme => theme.zIndex.drawer + 1, // Match PaperProps or slightly higher for the root container
        '& .MuiDrawer-paper': {
          // Already present in your old BaseDrawer for boxSizing
          boxSizing: 'border-box',
        },
      }}
    >
      {/* Header - conditionally rendered */}
      {showHeader && (
        <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {titleIcon}
            <Typography variant="h6">{title}</Typography>
          </Stack>
        </Box>
      )}

      {/* Content */}
      <Box
        sx={{
          p: showHeader ? 3 : 0,
          flex: 1,
          overflowY: 'auto',
        }}
      >
        {children}
      </Box>

      {/* Footer */}
      <Box
        sx={{
          p: 3,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        {error && (
          <Typography color="error" variant="body2" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}
        <Stack direction="row" spacing={2} justifyContent="flex-end">
          {closeButtonText && (
            <Button onClick={onClose} disabled={loading}>
              {closeButtonText}
            </Button>
          )}
          {onSave && (
            <Button
              variant="contained"
              onClick={onSave}
              disabled={loading || saveDisabled}
              startIcon={
                loading ? (
                  <CircularProgress size={16} color="inherit" />
                ) : undefined
              }
              sx={{
                '&.Mui-disabled': {
                  bgcolor: 'action.disabledBackground',
                  color: 'action.disabled',
                },
              }}
            >
              {loading ? 'Executing...' : saveButtonText}
            </Button>
          )}
        </Stack>
      </Box>
    </Drawer>
  );
}
