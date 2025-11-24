'use client';

import * as React from 'react';
import { Box, Typography, Paper, Container } from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useSession } from 'next-auth/react';
import { useState, useEffect } from 'react';
import TeamInviteForm from './components/TeamInviteForm';
import TeamMembersGrid from './components/TeamMembersGrid';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default function TeamPage() {
  const { data: session } = useSession();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [userCount, setUserCount] = useState(0);
  const { markStepComplete, progress, activeTour } = useOnboarding();

  // Enable tour for this page
  useOnboardingTour('invite');

  // Fetch user count to check if invites have been sent
  useEffect(() => {
    const fetchUserCount = async () => {
      if (!session?.session_token) return;

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const usersClient = apiFactory.getUsersClient();
        const response = await usersClient.getUsers({ skip: 0, limit: 1 });
        setUserCount(response.total || 0);
      } catch (error) {
        // Silently fail
      }
    };

    fetchUserCount();
  }, [session?.session_token, refreshTrigger]);

  // Mark step as complete when user count is > 1 (more than just the owner)
  useEffect(() => {
    if (userCount > 1 && !progress.usersInvited) {
      markStepComplete('usersInvited');
    }
  }, [userCount, progress.usersInvited, markStepComplete]);

  const handleInvitesSent = (emails: string[]) => {
    // Trigger refresh of team members grid and user count
    setRefreshTrigger(prev => prev + 1);
    // Mark as complete if invites were successfully sent
    if (emails.length > 0 && !progress.usersInvited) {
      markStepComplete('usersInvited');
    }
  };

  return (
    <PageContainer>
      {/* Invitation Section */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <TeamInviteForm
          onInvitesSent={handleInvitesSent}
          disableDuringTour={activeTour === 'invite'}
        />
      </Paper>

      {/* Team Members Grid */}
      <Paper sx={{ p: 3 }}>
        <TeamMembersGrid refreshTrigger={refreshTrigger} />
      </Paper>
    </PageContainer>
  );
}
