'use client';

import * as React from 'react';
import { Box, Typography, Paper, Alert, CircularProgress } from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useSession } from 'next-auth/react';
import { useState, useEffect, useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';
import OrganizationDetailsForm from './components/OrganizationDetailsForm';
import ContactInformationForm from './components/ContactInformationForm';
import DangerZone from './components/DangerZone';

export default function OrganizationSettingsPage() {
  const { data: session } = useSession();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      } catch (err: any) {
        console.error('Error fetching organization:', err);
        setError(err.message || 'Failed to load organization details');
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
    // Silently refresh organization data without showing loading spinner
    fetchOrganization(false);
  }, [fetchOrganization]);

  if (initialLoading) {
    return (
      <PageContainer title="Overview">
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer title="Overview">
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      </PageContainer>
    );
  }

  if (!organization) {
    return (
      <PageContainer title="Overview">
        <Alert severity="warning" sx={{ mb: 3 }}>
          No organization found. Please contact support.
        </Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Overview">
      {/* Basic Information Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ mb: 2 }}>
          Basic Information
        </Typography>
        <OrganizationDetailsForm
          organization={organization}
          sessionToken={session?.session_token || ''}
          onUpdate={handleUpdate}
        />
      </Paper>

      {/* Contact Information Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ mb: 2 }}>
          Contact Information
        </Typography>
        <ContactInformationForm
          organization={organization}
          sessionToken={session?.session_token || ''}
          onUpdate={handleUpdate}
        />
      </Paper>

      {/* Danger Zone Section */}
      <Paper sx={{ p: 3 }}>
        <DangerZone
          organization={organization}
          sessionToken={session?.session_token || ''}
        />
      </Paper>
    </PageContainer>
  );
}
