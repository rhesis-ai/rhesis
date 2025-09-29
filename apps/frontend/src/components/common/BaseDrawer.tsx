'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  Button,
  Stack,
  // Divider // Keep or remove based on whether header/footer have borders
} from '@mui/material';

interface BaseDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  loading?: boolean;
  onSave?: () => void;
  error?: string;
  saveButtonText?: string;
  width?: number | string; // Add width prop
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
  children,
  loading = false,
  onSave,
  error,
  saveButtonText = 'Save Changes',
  width = 600, // Default width
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
      {/* Optional: Re-introduce explicit Header/Content/Footer Box structure if desired */}
      {/* Header */}
      <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6">{title}</Typography>
      </Box>

      {/* Content */}
      <Box
        sx={{
          p: 3,
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
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          {onSave && (
            <Button variant="contained" onClick={onSave} disabled={loading}>
              {saveButtonText}
            </Button>
          )}
        </Stack>
      </Box>
    </Drawer>
  );
}
