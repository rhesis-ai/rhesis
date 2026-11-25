'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { normalizeTabParam, TAB_KEYS, TAB_LABELS } from './components/tabs';

// Usage is a tabbed section page with a 2-item breadcrumb trail and no
// header FABs.
export default function UsageLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  return (
    <PageDetailSkeleton
      actionCount={0}
      breadcrumbCount={2}
      tabs={TAB_KEYS.map(key => TAB_LABELS[key])}
      activeTab={TAB_KEYS.indexOf(activeKey)}
    />
  );
}
