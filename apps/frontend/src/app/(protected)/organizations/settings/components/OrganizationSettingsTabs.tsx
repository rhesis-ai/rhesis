'use client';

import React, { useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { getOrgSettingsTabs } from '@/lib/extension-registries';
import OrganizationDetailsForm from './OrganizationDetailsForm';
import ContactInformationForm from './ContactInformationForm';
import DangerZone from './DangerZone';

interface BuiltInTab {
  id: string;
  label: string;
  order: number;
  dynamic: false;
}

interface DynamicTab {
  id: string;
  label: string;
  order: number;
  dynamic: true;
  component: React.ComponentType;
}

type MergedTab = BuiltInTab | DynamicTab;

const BUILT_IN_TABS: BuiltInTab[] = [
  { id: 'information', label: 'Information', order: 0, dynamic: false },
  { id: 'danger', label: 'Danger zone', order: 999, dynamic: false },
];

const LEGACY_TAB_MAP: Record<string, string> = {
  'sso-api': 'sso',
};

interface OrganizationSettingsTabsProps {
  organization: Organization;
  onUpdate: () => void;
}

function resolveTabParam(
  param: string | null,
  validIds: readonly string[]
): string {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && validIds.includes(param)) {
    return param;
  }
  return 'information';
}

export default function OrganizationSettingsTabs({
  organization,
  onUpdate,
}: OrganizationSettingsTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const dynamicTabs = useMemo(() => getOrgSettingsTabs(), []);

  const allTabs: MergedTab[] = useMemo(() => {
    const merged: MergedTab[] = [
      ...BUILT_IN_TABS,
      ...dynamicTabs.map((t): DynamicTab => ({
        id: t.id,
        label: t.title,
        order: t.order,
        dynamic: true,
        component: t.component,
      })),
    ];
    return merged.sort((a, b) => a.order - b.order);
  }, [dynamicTabs]);

  const tabIds = useMemo(() => allTabs.map(t => t.id), [allTabs]);

  const activeTab = useMemo(() => {
    const key = resolveTabParam(searchParams.get('tab'), tabIds);
    const idx = tabIds.indexOf(key);
    return idx >= 0 ? idx : 0;
  }, [searchParams, tabIds]);

  const handleTabChange = useCallback(
    (newIndex: number) => {
      const key = allTabs[newIndex]?.id;
      if (!key) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams, allTabs]
  );

  const indexOf = (id: string) => allTabs.findIndex(t => t.id === id);

  const navTabs = allTabs.map((tab, index) => ({
    key: tab.id,
    label: tab.label,
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

      <DetailTabPanel
        value={activeTab}
        index={indexOf('information')}
        prefix="org-settings"
      >
        <OrganizationDetailsForm
          organization={organization}
          onUpdate={onUpdate}
        />
        <ContactInformationForm
          organization={organization}
          onUpdate={onUpdate}
        />
      </DetailTabPanel>

      {allTabs
        .filter((tab): tab is DynamicTab => tab.dynamic)
        .map(tab => {
          const TabComponent = tab.component;
          return (
            <DetailTabPanel
              key={tab.id}
              value={activeTab}
              index={indexOf(tab.id)}
              prefix="org-settings"
            >
              <TabComponent />
            </DetailTabPanel>
          );
        })}

      <DetailTabPanel
        value={activeTab}
        index={indexOf('danger')}
        prefix="org-settings"
      >
        <SectionCard title="Danger Zone" variant="danger">
          <DangerZone organization={organization} />
        </SectionCard>
      </DetailTabPanel>
    </Box>
  );
}
