'use client';

import React, { useState } from 'react';
import { Box, Button, Divider, Typography } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import AddIcon from '@mui/icons-material/Add';
import { useRouter } from 'next/navigation';
import { BORDER_RADIUS } from '@/styles/theme';
import ProjectSwitcherDrawer from '@/components/navigation/ProjectSwitcherDrawer';
import { useActiveProject } from '@/contexts/ActiveProjectContext';

/**
 * Shown when the authenticated user belongs to an organization but has no
 * project memberships.  Offers two exits:
 *  1. Create a new project (which auto-enrolls them as owner).
 *  2. Refresh the switcher in case an admin just added them.
 */
export default function NoProjectAccess() {
  const router = useRouter();
  const { refresh } = useActiveProject();
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const handleRefresh = async () => {
    await refresh();
    setSwitcherOpen(true);
  };

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
          maxWidth: 440,
          width: '100%',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
        }}
      >
        {/* Icon */}
        <Box
          sx={{
            width: 72,
            height: 72,
            borderRadius: '50%',
            bgcolor: theme =>
              theme.palette.mode === 'light' ? 'grey.100' : 'grey.900',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <LockOutlinedIcon
            sx={{ fontSize: 36, color: 'text.secondary' }}
          />
        </Box>

        {/* Heading */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Typography variant="h5" fontWeight={700}>
            No project access
          </Typography>
          <Typography variant="body1" color="text.secondary">
            You are not a member of any project yet. Ask an administrator to add
            you to a project, or create a new one.
          </Typography>
        </Box>

        {/* Actions */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            width: '100%',
          }}
        >
          <Button
            variant="contained"
            size="large"
            startIcon={<AddIcon />}
            onClick={() => router.push('/projects/create-new')}
            sx={{ borderRadius: BORDER_RADIUS.sm }}
          >
            Create a new project
          </Button>

          <Divider>
            <Typography variant="caption" color="text.disabled">
              or
            </Typography>
          </Divider>

          <Button
            variant="outlined"
            size="large"
            onClick={handleRefresh}
            sx={{ borderRadius: BORDER_RADIUS.sm }}
          >
            I&apos;ve been added — check again
          </Button>
        </Box>
      </Box>

      {/* Switcher drawer — opens after refresh if projects are now available */}
      <ProjectSwitcherDrawer
        open={switcherOpen}
        onClose={() => setSwitcherOpen(false)}
      />
    </Box>
  );
}
