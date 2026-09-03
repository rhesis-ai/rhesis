'use client';

import * as React from 'react';
import { Alert } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import { useOrganization } from '@/contexts/OrganizationContext';
import { OrgSettingsProvider } from '@/contexts/OrgSettingsContext';
import OrganizationSettingsTabs from './OrganizationSettingsTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { User } from '@/utils/api-client/interfaces/user';

interface OrganizationSettingsPageClientProps {
  /** Server-fetched first page of the team list — when present, the Team tab skips its initial client fetch. */
  initialTeamData?: User[];
  initialTeamTotalCount?: number;
}

export default function OrganizationSettingsPageClient({
  initialTeamData,
  initialTeamTotalCount = 0,
}: OrganizationSettingsPageClientProps) {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Organization.READ
  );
  const { organization, refresh } = useOrganization();

  const organizationName = organization?.name || 'Organization';

  const breadcrumbs = [
    { label: organizationName, href: '/organizations' },
    { label: 'Organization Settings', href: '/organizations/settings' },
  ];

  const pageHeader = {
    title: 'Organization Settings',
    description:
      "Manage your organization's profile, contact details, and security settings.",
    breadcrumbs,
  };

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="organization settings" />;

  if (!organization) {
    return (
      <PageLayout {...pageHeader}>
        <Alert severity="warning" sx={{ mb: 3 }}>
          No organization found. Please contact support.
        </Alert>
      </PageLayout>
    );
  }

  return (
    <PageLayout {...pageHeader}>
      <OrgSettingsProvider
        value={{
          organization,
          onUpdate: refresh,
          initialTeam: initialTeamData && {
            data: initialTeamData,
            totalCount: initialTeamTotalCount,
          },
        }}
      >
        <OrganizationSettingsTabs
          organization={organization}
          onUpdate={refresh}
        />
      </OrgSettingsProvider>
    </PageLayout>
  );
}
