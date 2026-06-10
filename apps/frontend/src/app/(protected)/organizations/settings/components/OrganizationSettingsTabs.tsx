'use client';

import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabNav from '@/components/common/DetailTabNav';
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

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label:
      key === 'information'
        ? 'Information'
        : key === 'sso-api'
          ? 'SSO & API'
          : 'Danger zone',
    id: `org-settings-tab-${index}`,
    'aria-controls': `org-settings-tabpanel-${index}`,
  }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Organization settings sections"
      />

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
