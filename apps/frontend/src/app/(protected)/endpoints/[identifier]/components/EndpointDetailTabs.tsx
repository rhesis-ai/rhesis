'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  TAB_KEYS,
  tabIndexFromKey,
  type EndpointTabKey,
} from './endpoint-detail-shared';
import EndpointOverviewTab from './EndpointOverviewTab';
import EndpointConnectionTab from './EndpointConnectionTab';
import EndpointMappingsTab from './EndpointMappingsTab';
import EndpointTestTab from './EndpointTestTab';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`endpoint-detail-tabpanel-${index}`}
      aria-labelledby={`endpoint-detail-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const TAB_LABELS: Record<EndpointTabKey, string> = {
  overview: 'Overview',
  connection: 'Connection',
  mappings: 'Mappings',
  test: 'Test',
};

export default function EndpointDetailTabs() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = tabIndexFromKey(searchParams.get('tab'));

  const handleTabChange = useCallback(
    (newValue: number) => {
      const key = TAB_KEYS[newValue];
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

      <TabPanel value={activeTab} index={0}>
        <EndpointOverviewTab />
      </TabPanel>
      <TabPanel value={activeTab} index={1}>
        <EndpointConnectionTab />
      </TabPanel>
      <TabPanel value={activeTab} index={2}>
        <EndpointMappingsTab />
      </TabPanel>
      <TabPanel value={activeTab} index={3}>
        <EndpointTestTab />
      </TabPanel>
    </Box>
  );
}
