'use client';

import * as React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  CircularProgress,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { alpha } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useSession } from 'next-auth/react';
import { useState, useEffect, useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';
import OrganizationDetailsForm from './components/OrganizationDetailsForm';
import ContactInformationForm from './components/ContactInformationForm';
import DangerZone from './components/DangerZone';
import { OrgSettingsProvider } from '@/contexts/OrgSettingsContext';
import { getOrgSettingsSections } from '@/lib/extension-registries';

/**
 * Visual container for one settings section.
 *
 * Each section renders as a card-styled `Accordion` so the operator can
 * collapse the noisier sections (SSO, API Clients, Danger Zone) and
 * focus on what they're editing. Sections start collapsed by default;
 * the page opts the most-edited card (Basic Information) into being
 * expanded on first load.
 */
function SettingsSection({
  title,
  titleColor,
  borderColor,
  background,
  defaultExpanded = false,
  children,
}: {
  title: string;
  titleColor?: string;
  borderColor?: string;
  background?: string | ((theme: Theme) => string);
  defaultExpanded?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      disableGutters
      elevation={1}
      sx={{
        mb: 3,
        borderRadius: 1,
        border: borderColor ? '1px solid' : undefined,
        borderColor,
        backgroundColor: background,
        '&:before': { display: 'none' },
        '&.Mui-expanded': { mb: 3 },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{ px: 3, py: 1 }}
      >
        <Typography variant="h6" sx={{ color: titleColor }}>
          {title}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 3, pb: 3, pt: 0 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

export default function OrganizationSettingsPage() {
  const { data: session } = useSession();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Registrations happen at module load via apps/frontend/src/ee_bootstrap.ts,
  // so by the time this client component renders the list is complete.
  // The registry returns a stable, frozen reference so this read does
  // not churn React identity across renders.
  const extensionSections = getOrgSettingsSections();

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
    { title: organizationName, path: '/organizations' },
    { title: 'Organization Settings', path: '/organizations/settings' },
  ];

  if (initialLoading) {
    return (
      <PageContainer title="Overview" breadcrumbs={breadcrumbs}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer title="Overview" breadcrumbs={breadcrumbs}>
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      </PageContainer>
    );
  }

  if (!organization) {
    return (
      <PageContainer title="Overview" breadcrumbs={breadcrumbs}>
        <Alert severity="warning" sx={{ mb: 3 }}>
          No organization found. Please contact support.
        </Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Overview" breadcrumbs={breadcrumbs}>
      <SettingsSection title="Basic Information" defaultExpanded>
        <OrganizationDetailsForm
          organization={organization}
          sessionToken={session?.session_token || ''}
          onUpdate={handleUpdate}
        />
      </SettingsSection>

      <SettingsSection title="Contact Information">
        <ContactInformationForm
          organization={organization}
          sessionToken={session?.session_token || ''}
          onUpdate={handleUpdate}
        />
      </SettingsSection>

      {/* EE-registered sections (e.g. SSO) -- discovered via the
          extension registry rather than imported by name. Sections
          read context they need from `useOrgSettings()` and apply
          their own `<FeatureGate>` wrapping; the page just composes. */}
      <OrgSettingsProvider
        value={{
          organization,
          sessionToken: session?.session_token || '',
          onUpdate: handleUpdate,
        }}
      >
        {extensionSections.map(section => {
          const Section = section.component;
          return (
            <SettingsSection key={section.id} title={section.title}>
              <Section />
            </SettingsSection>
          );
        })}
      </OrgSettingsProvider>

      <SettingsSection
        title="Danger Zone"
        titleColor="error.main"
        borderColor="error.light"
        background={theme => alpha(theme.palette.error.main, 0.05)}
      >
        <DangerZone
          organization={organization}
          sessionToken={session?.session_token || ''}
        />
      </SettingsSection>
    </PageContainer>
  );
}
