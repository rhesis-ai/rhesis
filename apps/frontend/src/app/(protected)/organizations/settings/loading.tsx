'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { getOrgSettingsTabs } from '@/lib/extension-registries';
import { activeTabIndex, mergeOrgSettingsTabs } from './components/tabs';

// Organization settings is a tabbed section page with a 2-item breadcrumb
// trail and no header FABs. Its tabs come from the same registry the page
// reads, so registered tabs (Team, EE ones) show up here too.
export default function OrganizationSettingsLoading() {
  const param = useSearchParams().get('tab');
  const tabs = mergeOrgSettingsTabs(getOrgSettingsTabs());
  return (
    <PageDetailSkeleton
      actionCount={0}
      breadcrumbCount={2}
      tabs={tabs.map(tab => tab.label)}
      activeTab={activeTabIndex(
        param,
        tabs.map(tab => tab.id)
      )}
    />
  );
}
