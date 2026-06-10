'use client';

import React, { useCallback, useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { getOrgSettingsSections } from '@/lib/extension-registries';
import OrganizationDetailsForm from './OrganizationDetailsForm';
import ContactInformationForm from './ContactInformationForm';
import DangerZone from './DangerZone';

const TAB_KEYS = ['information', 'sso', 'api', 'danger'] as const;
type OrgSettingsTabKey = (typeof TAB_KEYS)[number];

const LEGACY_TAB_MAP: Record<string, OrgSettingsTabKey> = {
  'sso-api': 'sso',
};

const TAB_SECTION_IDS: Record<'sso' | 'api', Set<string>> = {
  sso: new Set(['sso']),
  api: new Set(['api-clients']),
};

const TAB_UNAVAILABLE_COPY: Record<'sso' | 'api', string> = {
  sso: 'SSO settings are not available for this installation.',
  api: 'API client settings are not available for this installation.',
};

interface OrganizationSettingsTabsProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

function normalizeTabParam(param: string | null): OrgSettingsTabKey {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && TAB_KEYS.includes(param as OrgSettingsTabKey)) {
    return param as OrgSettingsTabKey;
  }
  return 'information';
}

const TAB_LABELS: Record<OrgSettingsTabKey, string> = {
  information: 'Information',
  sso: 'SSO',
  api: 'API',
  danger: 'Danger zone',
};

export default function OrganizationSettingsTabs({
  organization,
  sessionToken,
  onUpdate,
}: OrganizationSettingsTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = (() => {
    const key = normalizeTabParam(searchParams.get('tab'));
    return TAB_KEYS.indexOf(key);
  })();

  const handleTabChange = useCallback(
    (newIndex: number) => {
      const key = TAB_KEYS[newIndex];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const extensionSections = useMemo(() => getOrgSettingsSections(), []);

  const sectionsForTab = (tab: 'sso' | 'api') =>
    extensionSections.filter(section => TAB_SECTION_IDS[tab].has(section.id));

  const renderExtensionTab = (tab: 'sso' | 'api') => {
    const sections = sectionsForTab(tab);
    if (sections.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary">
          {TAB_UNAVAILABLE_COPY[tab]}
        </Typography>
      );
    }
    return sections.map(section => {
      const Section = section.component;
      if (section.id === 'api-clients') {
        return <Section key={section.id} />;
      }
      return (
        <SectionCard key={section.id} title={section.title}>
          <Section />
        </SectionCard>
      );
    });
  };

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
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
        {renderExtensionTab('sso')}
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="org-settings">
        {renderExtensionTab('api')}
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="org-settings">
        <SectionCard title="Danger Zone" variant="danger">
          <DangerZone organization={organization} sessionToken={sessionToken} />
        </SectionCard>
      </DetailTabPanel>
    </Box>
  );
}
