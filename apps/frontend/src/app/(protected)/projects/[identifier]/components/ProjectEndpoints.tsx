'use client';

import * as React from 'react';
import { useCallback, useState } from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
import { useSession } from 'next-auth/react';
import EndpointsGrid from '@/app/(protected)/endpoints/components/EndpointsGrid';
import EndpointCreateDrawer from '@/app/(protected)/endpoints/components/EndpointCreateDrawer';
import { AddIcon } from '@/components/icons';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';

interface ProjectEndpointsProps {
  projectId: string;
}

export default function ProjectEndpoints({ projectId }: ProjectEndpointsProps) {
  const { status } = useSession();
  const canCreate = useCan(Capability.Endpoint.CREATE);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const invalidateUsage = useInvalidateUsage();

  const handleCreate = useCallback(() => setDrawerOpen(true), []);

  const handleCreated = useCallback(() => {
    setDrawerOpen(false);
    setRefreshTrigger(prev => prev + 1);
    invalidateUsage();
  }, [invalidateUsage]);

  if (!isAuthenticated(status)) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">No session token available</Typography>
      </Box>
    );
  }

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Can capability={Capability.Endpoint.CREATE}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon sx={{ fontSize: 20 }} />}
            onClick={handleCreate}
            sx={sectionEditButtonSx}
          >
            New Endpoint
          </Button>
        </Can>
      </Box>

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
          projectId={projectId}
          canCreate={canCreate}
          onCreateClick={handleCreate}
          refreshTrigger={refreshTrigger}
        />
      </Paper>

      <EndpointCreateDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCreated={handleCreated}
        projectId={projectId}
      />
    </>
  );
}
