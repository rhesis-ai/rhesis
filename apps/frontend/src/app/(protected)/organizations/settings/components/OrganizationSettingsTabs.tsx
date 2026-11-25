'use client';

import { useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { SectionCard } from '@/components/common/SectionCard';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { getOrgSettingsTabs } from '@/lib/extension-registries';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { detailPageTitle } from '@/utils/document-title';
import OrganizationDetailsForm from './OrganizationDetailsForm';
import ContactInformationForm from './ContactInformationForm';
import BrandingColorsForm from './BrandingColorsForm';
import BrandingFaviconForm from './BrandingFaviconForm';
import BrandingFontForm from './BrandingFontForm';
import OrganizationCurrencyForm from './OrganizationCurrencyForm';
import OrganizationAccessibilityForm from './OrganizationAccessibilityForm';
import DangerZone from './DangerZone';
import { activeTabIndex, mergeOrgSettingsTabs, type DynamicTab } from './tabs';

interface OrganizationSettingsTabsProps {
  organization: Organization;
  onUpdate: () => void;
}

export default function OrganizationSettingsTabs({
  organization,
  onUpdate,
}: OrganizationSettingsTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const dynamicTabs = useMemo(() => getOrgSettingsTabs(), []);

  const allTabs = useMemo(
    () => mergeOrgSettingsTabs(dynamicTabs),
    [dynamicTabs]
  );

  const tabIds = useMemo(() => allTabs.map(t => t.id), [allTabs]);

  const activeTab = useMemo(
    () => activeTabIndex(searchParams.get('tab'), tabIds),
    [searchParams, tabIds]
  );

  // Registered tabs (Team, …) are their own page; the built-in ones are "Settings".
  const activeTabInfo = allTabs[activeTab];
  useDocumentTitle(
    detailPageTitle(
      activeTabInfo?.dynamic ? activeTabInfo.label : 'Settings',
      'Organization'
    )
  );

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

  // DetailTabPanel spaces its content from the nav, as on every detail page.
  return (
    <Box>
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

      <DetailTabPanel
        value={activeTab}
        index={indexOf('branding')}
        prefix="org-settings"
      >
        <BrandingColorsForm organization={organization} onUpdate={onUpdate} />
        <BrandingFaviconForm organization={organization} onUpdate={onUpdate} />
        <BrandingFontForm organization={organization} onUpdate={onUpdate} />
      </DetailTabPanel>

      <DetailTabPanel
        value={activeTab}
        index={indexOf('preferences')}
        prefix="org-settings"
      >
        <OrganizationCurrencyForm
          organization={organization}
          onUpdate={onUpdate}
        />
        <OrganizationAccessibilityForm
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
        <SectionCard title="Danger zone" variant="danger">
          <DangerZone organization={organization} />
        </SectionCard>
      </DetailTabPanel>
    </Box>
  );
}
