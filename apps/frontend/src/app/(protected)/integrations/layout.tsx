'use client';

import * as React from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import { usePathname, useRouter } from 'next/navigation';

export default function IntegrationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  // Redirect to models if on the root integrations path
  React.useEffect(() => {
    if (pathname === '/integrations') {
      router.replace('/integrations/models');
    }
  }, [pathname, router]);

  const tabValue = React.useMemo(() => {
    if (pathname.includes('/models')) return 0;
    if (pathname.includes('/apis')) return 1;
    if (pathname.includes('/mcps')) return 2;
    return 0;
  }, [pathname]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    switch (newValue) {
      case 0:
        router.push('models');
        break;
      case 1:
        router.push('apis');
        break;
      case 2:
        router.push('mcps');
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
          <Tab label="Models" />
          <Tab label="APIs" />
          <Tab label="MCPs" />
        </Tabs>
      </Box>
      {children}
    </Box>
  );
}
