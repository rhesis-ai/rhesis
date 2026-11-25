'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS, tabIndexFromKey } from './utils/tab-key';

export default function TestRunDetailLoading() {
  const searchParams = useSearchParams();
  const tab = searchParams.get('tab');
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.testRuns)] }}
      // Annotations' count badge shows only once there are annotations, so
      // it has no placeholder.
      tabs={TAB_KEYS.map(key => TAB_LABELS[key])}
      // Same resolution TestRunMainView runs, ?selectedresult= included.
      activeTab={tabIndexFromKey(
        tab,
        Boolean(searchParams.get('selectedresult')) && !tab
      )}
    />
  );
}
