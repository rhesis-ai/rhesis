'use client';

import * as React from 'react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Box, Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionCardGridBleedSx } from '@/components/common/GridToolbar';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import TeamInviteDrawer from '../../team/components/TeamInviteDrawer';
import TeamMembersGrid from '../../team/components/TeamMembersGrid';

export default function TeamTab() {
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
      <SectionCard
        title="Team"
        subtitle="Invite colleagues and manage who has access to your organization."
        actions={
          <Can capability={Capability.Member.CREATE}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon sx={{ fontSize: 20 }} />}
              onClick={() => setInviteDrawerOpen(true)}
              disabled={isOnInviteTour}
              data-tour="invite-team-button"
              aria-label="Invite team members"
              sx={sectionEditButtonSx}
            >
              Invite members
            </Button>
          </Can>
        }
      >
        <Box sx={sectionCardGridBleedSx}>
          <TeamMembersGrid
            refreshTrigger={refreshTrigger}
            onTotalCountChange={handleTotalCountChange}
          />
        </Box>
      </SectionCard>

      <TeamInviteDrawer
        open={inviteDrawerOpen}
        onClose={() => setInviteDrawerOpen(false)}
        onInvitesSent={handleInvitesSent}
        disableDuringTour={isOnInviteTour}
      />
    </>
  );
}
