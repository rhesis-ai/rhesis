'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { normalizeTabParam, TAB_KEYS, TAB_LABELS } from './components/tabs';

// The trail depends on the endpoint (Projects › project › endpoint when it
// belongs to one, Endpoints › endpoint otherwise), so all of it waits.
export default function EndpointDetailLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  return (
    <PageDetailSkeleton
      breadcrumbCount={3}
      tabs={TAB_KEYS.map(key => TAB_LABELS[key])}
      activeTab={TAB_KEYS.indexOf(activeKey)}
    />
  );
}
