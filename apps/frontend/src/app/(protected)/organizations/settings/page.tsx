'use client';

import * as React from 'react';
import { Alert, Box, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import { useSession } from 'next-auth/react';
import { useState, useEffect, useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { OrgSettingsProvider } from '@/contexts/OrgSettingsContext';
import OrganizationSettingsTabs from './components/OrganizationSettingsTabs';
import AccessDenied from '@/components/common/AccessDenied';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

export default function OrganizationSettingsPage() {
  const { data: session } = useSession();
  const canRead = useCan(Capability.Organization.READ);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const organizationName = organization?.name || 'Organization';

  const fetchOrganization = useCallback(
    async (showLoading = false) => {
      if (!session?.session_token || !session?.user?.organization_id) {
        setInitialLoading(false);
        return;
      }

      try {
        if (showLoading) {
          setInitialLoading(true);
        }
        setError(null);
        const apiFactory = new ApiClientFactory(session.session_token);
        const organizationsClient = apiFactory.getOrganizationsClient();
        const orgData = await organizationsClient.getOrganization(
          session.user.organization_id
        );
        setOrganization(orgData);
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load organization details'
        );
      } finally {
        if (showLoading) {
          setInitialLoading(false);
        }
      }
    },
    [session]
  );

  useEffect(() => {
    fetchOrganization(true);
  }, [fetchOrganization]);

  const handleUpdate = useCallback(() => {
    fetchOrganization(false);
  }, [fetchOrganization]);

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

  if (!canRead) return <AccessDenied resource="organization settings" />;

  if (initialLoading) {
    return (
      <PageLayout {...pageHeader}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout {...pageHeader}>
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      </PageLayout>
    );
  }

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
          sessionToken: session?.session_token || '',
          onUpdate: handleUpdate,
        }}
      >
        <OrganizationSettingsTabs
          organization={organization}
          sessionToken={session?.session_token || ''}
          onUpdate={handleUpdate}
        />
      </OrgSettingsProvider>
    </PageLayout>
  );
}
