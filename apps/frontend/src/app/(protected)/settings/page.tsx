'use client';

import React from 'react';
import { Box } from '@mui/material';
import { PAGE_SECTION_GAP } from '@/styles/theme-constants';
import { PageLayout } from '@/components/layout/PageLayout';
import { useUserSettings } from '@/hooks/useUserSettings';
import PageLoadingState from '@/components/common/PageLoadingState';
import ProfileForm from './components/ProfileForm';
import SecuritySection from './components/SecuritySection';

export default function SettingsPage() {
  const { data: userSettings, isLoading } = useUserSettings();

  const breadcrumbs = [{ label: 'Settings', href: '/settings' }];

  const pageHeader = {
    title: 'Settings',
    description: 'Manage your profile and account.',
    breadcrumbs,
  };

  if (isLoading) return <PageLoadingState />;

  return (
    <PageLayout {...pageHeader}>
      <Box
        sx={{ display: 'flex', flexDirection: 'column', gap: PAGE_SECTION_GAP }}
      >
        <ProfileForm userSettings={userSettings} />
        <SecuritySection userSettings={userSettings} />
      </Box>
    </PageLayout>
  );
}
