'use client';

import * as React from 'react';
import { Alert, Box, CircularProgress } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import { useSession } from 'next-auth/react';
import { useState, useEffect, useCallback } from 'react';
import {
  fetchOrganization,
  invalidateOrganization,
} from '@/utils/api-client/organization-cache';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { OrgSettingsProvider } from '@/contexts/OrgSettingsContext';
import OrganizationSettingsTabs from './components/OrganizationSettingsTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

export default function OrganizationSettingsPage() {
  const { data: session } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Organization.READ
  );
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
        } else {
          // A refresh triggered after a mutation (e.g. saving a form) must
          // bypass the cache so the reloaded data reflects the change.
          invalidateOrganization();
        }
        setError(null);
        const orgData = await fetchOrganization(
          session.session_token,
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

  if (permsLoading) return <PageLoadingState />;
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
