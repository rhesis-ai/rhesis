'use client';

import React from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { TAB_KEYS, type EndpointTabKey } from './endpoint-detail-shared';
import EndpointOverviewTab from './EndpointOverviewTab';
import EndpointConnectionTab from './EndpointConnectionTab';
import EndpointMappingsTab from './EndpointMappingsTab';
import EndpointTestTab from './EndpointTestTab';

const TAB_LABELS: Record<EndpointTabKey, string> = {
  overview: 'Overview',
  connection: 'Connection',
  mappings: 'Mappings',
  test: 'Test',
};

export default function EndpointDetailTabs() {
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

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
        <EndpointMappingsTab />
      </DetailTabPanel>
      <DetailTabPanel value={activeTab} index={3} prefix="endpoint-detail">
        <EndpointTestTab />
      </DetailTabPanel>
    </Box>
  );
}
