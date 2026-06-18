'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import {
  TAB_KEYS,
  LEGACY_TAB_MAP,
  type EndpointTabKey,
} from './endpoint-detail-shared';
import EndpointOverviewTab from './EndpointOverviewTab';
import EndpointConnectionTab from './EndpointConnectionTab';
import EndpointMappingTab from './EndpointMappingTab';
import EndpointTestTab from './EndpointTestTab';

const TAB_LABELS: Record<EndpointTabKey, string> = {
  overview: 'Overview',
  connection: 'Connection',
  mapping: 'Mapping',
  test: 'Test',
};

function normalizeTabParam(param: string | null): EndpointTabKey {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && TAB_KEYS.includes(param as EndpointTabKey)) {
    return param as EndpointTabKey;
  }
  return 'overview';
}

export default function EndpointDetailTabs() {
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
    id: `endpoint-detail-tab-${index}`,
    'aria-controls': `endpoint-detail-tabpanel-${index}`,
  }));

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Endpoint detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="endpoint-detail">
        <EndpointOverviewTab />
      </DetailTabPanel>
      <DetailTabPanel value={activeTab} index={1} prefix="endpoint-detail">
        <EndpointConnectionTab />
      </DetailTabPanel>
      <DetailTabPanel value={activeTab} index={2} prefix="endpoint-detail">
        <EndpointMappingTab />
      </DetailTabPanel>
      <DetailTabPanel value={activeTab} index={3} prefix="endpoint-detail">
        <EndpointTestTab />
      </DetailTabPanel>
    </Box>
  );
}
