'use client';

import { useSearchParams } from 'next/navigation';
import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { normalizeTabParam, TAB_KEYS, TAB_LABELS } from './components/tabs';

export default function ProjectDetailLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.projects)] }}
      tabs={TAB_KEYS.map(key => TAB_LABELS[key])}
      activeTab={TAB_KEYS.indexOf(activeKey)}
    />
  );
}
