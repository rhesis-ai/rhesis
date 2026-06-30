'use client';

import React from 'react';
import { Box, CircularProgress } from '@mui/material';

/**
 * Neutral full-height loading state for page/section read guards.
 *
 * Rendered while ambient permissions are still resolving so a guarded page
 * shows a spinner instead of briefly flashing `<AccessDenied />` (the
 * permission-fetch window exists even for community/RBAC-off users while
 * feature flags load). Mirrors the centered layout of `AccessDenied`.
 */
export default function PageLoadingState() {
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
      <CircularProgress />
    </Box>
  );
}
