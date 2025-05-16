'use client';

import * as React from 'react';
import { 
  Drawer,
  Box,
  Typography,
  Button,
  Stack,
  Divider
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
}

// Utility function to filter out duplicates and invalid entries
export function filterUniqueValidOptions<T extends { id: string | number; name: string }>(options: T[]): T[] {
  // First, filter out entries with empty or invalid names
  const validOptions = options.filter(option => 
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
  saveButtonText = 'Save Changes'
}: BaseDrawerProps) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{
        keepMounted: false,
        slotProps: {
          backdrop: {
            sx: {
              backgroundColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      }}
      slotProps={{
        backdrop: {
          sx: {
            zIndex: 1200
          }
        }
      }}
      PaperProps={{
        sx: {
          width: 600,
          zIndex: 1300
        }
      }}
      sx={{
        zIndex: 1300,
        '& .MuiDrawer-paper': {
          boxSizing: 'border-box'
        }
      }}
    >
      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6">{title}</Typography>
        </Box>

        {/* Content */}
        <Box 
          sx={{ 
            flex: 1, 
            overflow: 'auto'
          }}
        >
          {/* Content wrapper with standardized styling */}
          <Box 
            sx={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: 2,
              p: 3
            }}
          >
            {children}
          </Box>
        </Box>

        {/* Footer */}
        <Box sx={{ p: 3, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
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
              <Button 
                variant="contained" 
                onClick={onSave}
                disabled={loading}
              >
                {saveButtonText}
              </Button>
            )}
          </Stack>
        </Box>
      </Box>
    </Drawer>
  );
} 