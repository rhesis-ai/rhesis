'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import AddIcon from '@mui/icons-material/Add';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import { BORDER_RADIUS, ELEVATION, GREYSCALE } from '@/styles/theme';
import TeamInviteDrawer from './components/TeamInviteDrawer';
import TeamMembersGrid from './components/TeamMembersGrid';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';

export default function TeamPage() {
  const searchParams = useSearchParams();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [inviteDrawerOpen, setInviteDrawerOpen] = useState(false);
  const { markStepComplete, progress, activeTour } = useOnboarding();

  const handleTotalCountChange = React.useCallback(
    (count: number) => {
      if (count > 1 && !progress.usersInvited) {
        markStepComplete('usersInvited');
      }
    },
    [progress.usersInvited, markStepComplete]
  );

  useOnboardingTour('invite');

  const tourParam = searchParams?.get('tour');
  const isOnInviteTour = tourParam === 'invite' || activeTour === 'invite';

  useEffect(() => {
    if (isOnInviteTour) {
      const timeout = setTimeout(() => setInviteDrawerOpen(true), 300);
      return () => clearTimeout(timeout);
    }
  }, [isOnInviteTour]);

  const handleInvitesSent = (emails: string[]) => {
    setRefreshTrigger(prev => prev + 1);
    if (emails.length > 0 && !progress.usersInvited) {
      markStepComplete('usersInvited');
    }
  };

  return (
    <>
      <PageLayout
        title="Team"
        description="Invite colleagues and manage who has access to your organization."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Fab
              icon={<AddIcon />}
              tooltip="Invite team members"
              onClick={() => setInviteDrawerOpen(true)}
              disabled={isOnInviteTour}
              data-tour="invite-team-button"
            />
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <Paper
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme =>
                `1px solid ${
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border
                }`,
              overflow: 'hidden',
            }}
          >
            <TeamMembersGrid
              refreshTrigger={refreshTrigger}
              onTotalCountChange={handleTotalCountChange}
            />
          </Paper>
        </Box>
      </PageLayout>

      <TeamInviteDrawer
        open={inviteDrawerOpen}
        onClose={() => setInviteDrawerOpen(false)}
        onInvitesSent={handleInvitesSent}
        disableDuringTour={isOnInviteTour}
      />
    </>
  );
}
