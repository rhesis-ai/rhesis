'use client';

import React, { useCallback, useMemo } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import { getOrgSettingsSections } from '@/lib/extension-registries';
import OrganizationDetailsForm from './OrganizationDetailsForm';
import ContactInformationForm from './ContactInformationForm';
import DangerZone from './DangerZone';

const TAB_KEYS = ['information', 'sso-api', 'danger'] as const;
type TabKey = (typeof TAB_KEYS)[number];

const SSO_API_SECTION_IDS = new Set(['sso', 'api-clients']);

function tabIndexFromKey(key: string | null): number {
  const idx = TAB_KEYS.indexOf(key as TabKey);
  return idx >= 0 ? idx : 0;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`org-settings-tabpanel-${index}`}
      aria-labelledby={`org-settings-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

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
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = tabIndexFromKey(searchParams.get('tab'));

  const extensionSections = useMemo(() => getOrgSettingsSections(), []);
  const ssoApiSections = useMemo(
    () =>
      extensionSections.filter(section => SSO_API_SECTION_IDS.has(section.id)),
    [extensionSections]
  );

  const handleTabChange = useCallback(
    (_event: React.SyntheticEvent, newValue: number) => {
      const key = TAB_KEYS[newValue];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
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

      <TabPanel value={activeTab} index={0}>
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
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
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
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <SectionCard title="Danger Zone" variant="danger">
          <DangerZone organization={organization} sessionToken={sessionToken} />
        </SectionCard>
      </TabPanel>
    </Box>
  );
}
