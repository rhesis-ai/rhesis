'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { AutoFixHighIcon } from '@/components/icons';

/**
 * Opens auto-configure. It sits on the Connection step because that's what it
 * fills (URL, method, headers, then the mappings), and the token typed there
 * lets its live probe authenticate.
 */
export default function QuickSetupBanner({ onOpen }: { onOpen: () => void }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1.25,
        bgcolor: theme =>
          alpha(
            theme.palette.primary.main,
            theme.palette.mode === 'dark' ? 0.16 : 0.1
          ),
      }}
    >
      <AutoFixHighIcon fontSize="small" sx={{ color: 'greyscale.title' }} />
      <Typography
        variant="body2"
        sx={{ flex: 1, minWidth: 0, color: 'greyscale.subtitle' }}
      >
        <Box
          component="span"
          sx={{ fontWeight: 700, color: 'greyscale.title', mr: 1 }}
        >
          Quickest setup
        </Box>
        Paste a cURL command, API docs or a sample request, and Rhesis fills in
        the connection and mapping.
      </Typography>
      <Button
        variant="contained"
        size="small"
        onClick={onOpen}
        sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
      >
        Auto-configure
      </Button>
    </Box>
  );
}
