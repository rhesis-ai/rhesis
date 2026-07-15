'use client';

import * as React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { useSession } from 'next-auth/react';
import EndpointsGrid from '@/app/(protected)/endpoints/components/EndpointsGrid';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface ProjectEndpointsProps {
  projectId: string;
  sessionToken: string;
}

export default function ProjectEndpoints({
  projectId,
  sessionToken,
}: ProjectEndpointsProps) {
  const { status } = useSession();

  if (!isAuthenticated(status)) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">No session token available</Typography>
      </Box>
    );
  }

  return (
    <Paper
      sx={{
        width: '100%',
        borderRadius: BORDER_RADIUS.md,
        boxShadow: ELEVATION.xs,
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        overflow: 'hidden',
      }}
    >
      <EndpointsGrid sessionToken={sessionToken} projectId={projectId} />
    </Paper>
  );
}
