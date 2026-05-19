'use client';

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import { SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from './sidebar-constants';
import { GREYSCALE } from '@/styles/theme';

interface AppShellProps {
  children: React.ReactNode;
  /** The sidebar node — typically <Sidebar /> */
  sidebar: React.ReactNode;
  /** Optional top-bar content (breadcrumbs, title, FAB cluster) */
  topBar?: React.ReactNode;
}

/**
 * Root layout shell.  A CSS-grid two-column layout:
 *   [sidebar (240 or 64px)] | [content area]
 *
 * The sidebar receives the collapse state via the SidebarCollapseContext so
 * that child components can react to it without prop-drilling.
 */
export interface SidebarCollapseContextValue {
  collapsed: boolean;
  toggle: () => void;
}

export const SidebarCollapseContext =
  React.createContext<SidebarCollapseContextValue>({
    collapsed: false,
    toggle: () => {},
  });

export function useSidebarCollapse() {
  return React.useContext(SidebarCollapseContext);
}

export function AppShell({ children, sidebar, topBar }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const toggle = () => setCollapsed(c => !c);

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <SidebarCollapseContext.Provider value={{ collapsed, toggle }}>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: `${sidebarWidth}px 1fr`,
          minHeight: '100vh',
          transition: 'grid-template-columns 0.2s ease',
        }}
      >
        {/* Sidebar column */}
        <Box
          component="nav"
          aria-label="Main navigation"
          sx={{
            width: sidebarWidth,
            flexShrink: 0,
            position: 'sticky',
            top: 0,
            height: '100vh',
            overflow: 'hidden',
            transition: 'width 0.2s ease',
            zIndex: theme => theme.zIndex.drawer,
            // Match the sidebar surface so no white bleeds around the edges
            bgcolor: theme =>
              theme.palette.mode === 'light'
                ? GREYSCALE.light.surface1
                : GREYSCALE.dark.surface1,
          }}
        >
          {sidebar}
        </Box>

        {/* Main content column */}
        <Box
          component="main"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: '100vh',
            minWidth: 0,
            bgcolor: 'background.default',
          }}
        >
          {topBar && (
            <Box
              component="header"
              sx={{
                flexShrink: 0,
                borderBottom: theme =>
                  `1px solid ${theme.palette.greyscale?.border ?? theme.palette.divider}`,
                bgcolor: 'background.paper',
                px: 4,
                py: 1,
              }}
            >
              {topBar}
            </Box>
          )}
          <Box
            sx={{
              flex: 1,
              p: 4,
            }}
          >
            {children}
          </Box>
        </Box>
      </Box>
    </SidebarCollapseContext.Provider>
  );
}
