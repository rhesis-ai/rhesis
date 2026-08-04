'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import UsageOverviewTab from './UsageOverviewTab';
import UsageOverTimeTab from './UsageOverTimeTab';

const TAB_KEYS = ['resources', 'timeline'] as const;
type UsageTabKey = (typeof TAB_KEYS)[number];

const TAB_LABELS: Record<UsageTabKey, string> = {
  resources: 'Resources',
  timeline: 'Timeline',
};

function normalizeTabParam(param: string | null): UsageTabKey {
  if (param && TAB_KEYS.includes(param as UsageTabKey)) {
    return param as UsageTabKey;
  }
  return 'resources';
}

export default function UsageDetailTabs() {
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

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
    id: `usage-detail-tab-${index}`,
    'aria-controls': `usage-detail-tabpanel-${index}`,
  }));

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Usage detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="usage-detail">
        <UsageOverviewTab />
      </DetailTabPanel>
      <DetailTabPanel value={activeTab} index={1} prefix="usage-detail">
        <UsageOverTimeTab />
      </DetailTabPanel>
    </Box>
  );
}
