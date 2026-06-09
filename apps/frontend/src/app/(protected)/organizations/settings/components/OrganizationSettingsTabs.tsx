'use client';

import React, { useMemo } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { getOrgSettingsSections } from '@/lib/extension-registries';
import OrganizationDetailsForm from './OrganizationDetailsForm';
import ContactInformationForm from './ContactInformationForm';
import DangerZone from './DangerZone';

const TAB_KEYS = ['information', 'sso-api', 'danger'] as const;

const SSO_API_SECTION_IDS = new Set(['sso', 'api-clients']);

interface OrganizationSettingsTabsProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

export default function OrganizationSettingsTabs({
  organization,
  sessionToken,
  onUpdate,
}: OrganizationSettingsTabsProps) {
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const extensionSections = useMemo(() => getOrgSettingsSections(), []);
  const ssoApiSections = useMemo(
    () =>
      extensionSections.filter(section => SSO_API_SECTION_IDS.has(section.id)),
    [extensionSections]
  );

  // MUI Tabs fires (_event, newValue) — adapt to hook signature
  const handleMuiTabChange = (
    _event: React.SyntheticEvent,
    newValue: number
  ) => {
    handleTabChange(newValue);
  };

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={handleMuiTabChange}
          aria-label="organization settings tabs"
        >
          <Tab
            label="Information"
            id="org-settings-tab-0"
            aria-controls="org-settings-tabpanel-0"
          />
          <Tab
            label="SSO & API"
            id="org-settings-tab-1"
            aria-controls="org-settings-tabpanel-1"
          />
          <Tab
            label="Danger zone"
            id="org-settings-tab-2"
            aria-controls="org-settings-tabpanel-2"
          />
        </Tabs>
      </Box>

      <DetailTabPanel value={activeTab} index={0} prefix="org-settings">
        <OrganizationDetailsForm
          organization={organization}
          sessionToken={sessionToken}
          onUpdate={onUpdate}
        />
        <ContactInformationForm
          organization={organization}
          sessionToken={sessionToken}
          onUpdate={onUpdate}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="org-settings">
        {ssoApiSections.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            SSO and API client settings are not available for this installation.
          </Typography>
        ) : (
          ssoApiSections.map(section => {
            const Section = section.component;
            return (
              <SectionCard key={section.id} title={section.title}>
                <Section />
              </SectionCard>
            );
          })
        )}
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="org-settings">
        <SectionCard title="Danger Zone" variant="danger">
          <DangerZone organization={organization} sessionToken={sessionToken} />
        </SectionCard>
      </DetailTabPanel>
    </Box>
  );
}
