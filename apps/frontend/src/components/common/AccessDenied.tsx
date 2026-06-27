'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';

interface AccessDeniedProps {
  /** Human-readable name of the resource the caller lacks access to. */
  resource?: string;
}

/**
 * Shown when the authenticated user lacks the capability to view a page or
 * section. Used for page-level read gating as the final defence against direct
 * URL access when the nav already hides the entry point.
 */
export default function AccessDenied({ resource }: AccessDeniedProps) {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 4,
      }}
    >
      <Box
        sx={{
          maxWidth: 400,
          width: '100%',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            bgcolor: theme =>
              theme.palette.mode === 'light' ? 'grey.100' : 'grey.900',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <LockOutlinedIcon sx={{ fontSize: 32, color: 'text.secondary' }} />
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Typography variant="h6" fontWeight={700}>
            Access denied
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {resource
              ? `You do not have permission to view ${resource}.`
              : 'You do not have permission to view this page.'}
            {' '}Contact your administrator if you need access.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
