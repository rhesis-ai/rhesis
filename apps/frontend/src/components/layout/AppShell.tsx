'use client';

import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import MenuIcon from '@mui/icons-material/Menu';
import { usePathname } from 'next/navigation';
import { SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from './sidebar-constants';
import { scaledVh } from '@/styles/viewport-scaling';

/** Routes that use the full main column (no AppShell content padding). */
const FULL_BLEED_PATH_PREFIXES = ['/architect'] as const;

function isFullBleedRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  return FULL_BLEED_PATH_PREFIXES.some(
    prefix => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

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

export const MAIN_CONTENT_ID = 'main-content';

const NAV_DRAWER_ID = 'main-navigation-drawer';

export function AppShell({ children, sidebar, topBar }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const toggle = () => setCollapsed(c => !c);
  const pathname = usePathname();
  const fullBleed = isFullBleedRoute(pathname);

  // Narrow viewports (small windows, 200-400 % zoom) get the sidebar as an
  // overlay so the content can reflow to the full width (WCAG 1.4.10).
  const theme = useTheme();
  const narrow = useMediaQuery(theme.breakpoints.down('md'), { noSsr: true });
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => setNavOpen(false), [pathname]);

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  if (narrow) {
    return (
      <SidebarCollapseContext.Provider
        // Inside the overlay the sidebar is always fully expanded.
        value={{ collapsed: false, toggle: () => setNavOpen(false) }}
      >
        <SkipLink />
        <Box sx={{ minHeight: scaledVh(), bgcolor: 'background.default' }}>
          <Box
            component="header"
            sx={{
              position: 'sticky',
              top: 0,
              zIndex: theme => theme.zIndex.appBar,
              display: 'flex',
              alignItems: 'center',
              px: 1,
              py: 0.5,
              bgcolor: theme => theme.palette.greyscale.surface1,
              borderBottom: theme => `1px solid ${theme.palette.divider}`,
            }}
          >
            <IconButton
              aria-label="Open navigation"
              aria-controls={NAV_DRAWER_ID}
              aria-expanded={navOpen}
              onClick={() => setNavOpen(true)}
            >
              <MenuIcon />
            </IconButton>
          </Box>
          <Drawer
            id={NAV_DRAWER_ID}
            open={navOpen}
            onClose={() => setNavOpen(false)}
            ModalProps={{ keepMounted: true }}
          >
            <Box
              component="nav"
              aria-label="Main navigation"
              sx={{
                width: SIDEBAR_WIDTH,
                height: '100%',
                bgcolor: theme => theme.palette.greyscale.surface1,
              }}
            >
              {sidebar}
            </Box>
          </Drawer>
          <MainContent topBar={topBar} fullBleed={fullBleed}>
            {children}
          </MainContent>
        </Box>
      </SidebarCollapseContext.Provider>
    );
  }

  return (
    <SidebarCollapseContext.Provider value={{ collapsed, toggle }}>
      <SkipLink />
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: `${sidebarWidth}px 1fr`,
          minHeight: scaledVh(),
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
            height: scaledVh(),
            overflow: 'hidden',
            transition: 'width 0.2s ease',
            zIndex: theme => theme.zIndex.drawer,
            bgcolor: theme => theme.palette.greyscale.surface1,
          }}
        >
          {sidebar}
        </Box>

        <MainContent topBar={topBar} fullBleed={fullBleed}>
          {children}
        </MainContent>
      </Box>
    </SidebarCollapseContext.Provider>
  );
}

/** First focusable element: lets keyboard users skip the navigation (2.4.1). */
function SkipLink() {
  return (
    <Box
      component="a"
      href={`#${MAIN_CONTENT_ID}`}
      sx={{
        position: 'fixed',
        top: theme => theme.spacing(1),
        left: theme => theme.spacing(1),
        zIndex: theme => theme.zIndex.tooltip + 1,
        px: 2,
        py: 1,
        borderRadius: 1,
        bgcolor: 'primary.main',
        color: 'primary.contrastText',
        fontWeight: 600,
        textDecoration: 'none',
        transform: 'translateY(-200%)',
        '&:focus': { transform: 'none' },
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: 'primary.dark',
          outlineOffset: 2,
        },
      }}
    >
      Skip to main content
    </Box>
  );
}

function MainContent({
  children,
  topBar,
  fullBleed,
}: {
  children: React.ReactNode;
  topBar?: React.ReactNode;
  fullBleed: boolean;
}) {
  return (
    <Box
      component="main"
      id={MAIN_CONTENT_ID}
      // Focus target for the skip link; not in the tab order otherwise.
      tabIndex={-1}
      sx={{
        '&:focus': { outline: 'none' },
        display: 'flex',
        flexDirection: 'column',
        minHeight: scaledVh(),
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
            px: { xs: 2, md: 4 },
            py: 1,
          }}
        >
          {topBar}
        </Box>
      )}
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          minWidth: 0,
          // Contained here, not on `main`, so a page whose content is
          // wider than the viewport scrolls only its body -- the
          // header above (breadcrumbs, title, FABs) stays put.
          overflowX: 'auto',
          ...(fullBleed
            ? {
                p: 0,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }
            : {
                p: { xs: 2, md: 4 },
                display: 'flex',
                flexDirection: 'column',
              }),
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
