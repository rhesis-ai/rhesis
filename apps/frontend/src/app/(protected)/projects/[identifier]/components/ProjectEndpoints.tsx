'use client';

import * as React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import EndpointsGrid from '@/app/(protected)/endpoints/components/EndpointsGrid';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface ProjectEndpointsProps {
  projectId: string;
  sessionToken: string;
}

export default function ProjectEndpoints({
  projectId,
  sessionToken,
}: ProjectEndpointsProps) {
  const [refreshKey, setRefreshKey] = React.useState(0);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  if (!sessionToken) {
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
      <EndpointsGrid
        sessionToken={sessionToken}
        refreshKey={refreshKey}
        onRefresh={handleRefresh}
        projectId={projectId}
      />
    </Paper>
  );
}
