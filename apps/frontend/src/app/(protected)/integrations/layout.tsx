'use client';

import * as React from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import { usePathname, useRouter } from 'next/navigation';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`integration-tabpanel-${index}`}
      aria-labelledby={`integration-tab-${index}`}
      {...other}
    >
      {value === index && <Box>{children}</Box>}
    </div>
  );
}

export default function IntegrationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  // Redirect to applications if on the root integrations path
  React.useEffect(() => {
    if (pathname === '/integrations') {
      router.replace('/integrations/applications');
    }
  }, [pathname, router]);

  const tabValue = React.useMemo(() => {
    if (pathname.includes('/applications')) return 0;
    if (pathname.includes('/tools')) return 1;
    if (pathname.includes('/models')) return 2;
    return 0;
  }, [pathname]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    switch (newValue) {
      case 0:
        router.push('applications');
        break;
      case 1:
        router.push('tools');
        break;
      case 2:
        router.push('models');
        break;
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="integration tabs"
          sx={{ px: 3 }}
        >
          <Tab label="Applications" />
          <Tab label="Tools" />
          <Tab label="Models" />
        </Tabs>
      </Box>
      {children}
    </Box>
  );
}
