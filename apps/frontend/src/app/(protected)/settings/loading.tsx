'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { activeTabIndex, TABS } from './components/tabs';

// Settings renders a 1-item breadcrumb trail and a tab bar over its section
// cards: no header FABs.
export default function SettingsLoading() {
  const param = useSearchParams().get('tab');
  return (
    <PageDetailSkeleton
      actionCount={0}
      breadcrumbCount={1}
      tabs={TABS.map(tab => tab.label)}
      activeTab={activeTabIndex(param)}
    />
  );
}
