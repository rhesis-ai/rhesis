'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box } from '@mui/material';
import AppSidebar, {
  SIDEBAR_EXPANDED_WIDTH,
  SIDEBAR_COLLAPSED_WIDTH,
} from '../navigation/AppSidebar';
import { type NavigationItem } from '@/types/navigation';

const SIDEBAR_STATE_KEY = 'sidebar-expanded';

interface AppLayoutProps {
  navigation: NavigationItem[];
  children: React.ReactNode;
}

export default function AppLayout({ navigation, children }: AppLayoutProps) {
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_STATE_KEY);
    if (stored !== null) {
      setExpanded(stored === 'true');
    }
  }, []);

  const handleToggle = useCallback(() => {
    setExpanded(prev => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_STATE_KEY, String(next));
      return next;
    });
  }, []);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppSidebar
        navigation={navigation}
        expanded={expanded}
        onToggle={handleToggle}
      />
      <Box
        component="main"
        sx={{
          flex: 1,
          minWidth: 0,
          width: `calc(100% - ${expanded ? SIDEBAR_EXPANDED_WIDTH : SIDEBAR_COLLAPSED_WIDTH}px)`,
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.default',
          transition: 'width 200ms ease',
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
