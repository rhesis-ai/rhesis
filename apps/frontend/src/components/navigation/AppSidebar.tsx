'use client';

import React, { useState, useMemo } from 'react';
import { Box, IconButton, Tooltip, SvgIcon } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

function LeftPanelCloseIcon(props: React.ComponentProps<typeof SvgIcon>) {
  return (
    <SvgIcon {...props} viewBox="0 0 24 24">
      <path
        d="M3 6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6Zm2 0v12a1 1 0 0 0 1 1h3V5H6a1 1 0 0 0-1 1Zm6-1v14h7a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-7Z"
        fill="currentColor"
        fillRule="evenodd"
        clipRule="evenodd"
      />
      <path
        d="M16.5 8.5 13 12l3.5 3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </SvgIcon>
  );
}
import NavItem from './NavItem';
import NavCategoryHeader from './NavCategoryHeader';
import NavCompanyBranding from './NavCompanyBranding';
import NavScrollArea from './NavScrollArea';
import CompanyMenu from './CompanyMenu';
import SidebarFooter from './SidebarFooter';
import { type NavigationItem } from '@/types/navigation';
import { useSession } from 'next-auth/react';

export const SIDEBAR_EXPANDED_WIDTH = 260;
export const SIDEBAR_COLLAPSED_WIDTH = 68;

interface AppSidebarProps {
  navigation: NavigationItem[];
  expanded: boolean;
  onToggle: () => void;
}

interface NavGroup {
  header?: string;
  items: NavigationItem[];
}

function groupNavItems(items: NavigationItem[]): NavGroup[] {
  const groups: NavGroup[] = [];
  let currentGroup: NavGroup = { items: [] };

  for (const item of items) {
    if (item.kind === 'header') {
      if (currentGroup.items.length > 0 || currentGroup.header) {
        groups.push(currentGroup);
      }
      currentGroup = { header: item.title, items: [] };
    } else if (item.kind === 'divider') {
      if (currentGroup.items.length > 0 || currentGroup.header) {
        groups.push(currentGroup);
      }
      currentGroup = { items: [] };
    } else {
      currentGroup.items.push(item);
    }
  }
  if (currentGroup.items.length > 0 || currentGroup.header) {
    groups.push(currentGroup);
  }

  return groups;
}

function filterSuperuserItems(
  items: NavigationItem[],
  isSuperuser: boolean
): NavigationItem[] {
  return items.filter(item => {
    if ('requireSuperuser' in item && item.requireSuperuser && !isSuperuser) {
      return false;
    }
    return true;
  });
}

export default function AppSidebar({
  navigation,
  expanded,
  onToggle,
}: AppSidebarProps) {
  const { data: session } = useSession();
  const isSuperuser = !!(session?.user as Record<string, unknown>)
    ?.is_superuser;
  const [companyMenuAnchor, setCompanyMenuAnchor] =
    useState<HTMLElement | null>(null);

  const mainNavItems = useMemo(() => {
    const filtered = navigation.filter(
      item =>
        item.kind !== 'link' &&
        !(item.kind === 'page' && item.segment === 'organizations')
    );
    return filterSuperuserItems(filtered, isSuperuser);
  }, [navigation, isSuperuser]);

  const groups = useMemo(() => groupNavItems(mainNavItems), [mainNavItems]);
  const mini = !expanded;

  const handleCompanyMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setCompanyMenuAnchor(event.currentTarget);
  };

  const handleCompanyMenuClose = () => {
    setCompanyMenuAnchor(null);
  };

  const renderItem = (item: NavigationItem) => {
    if (item.kind === 'page') {
      return (
        <NavItem
          key={item.segment}
          icon={item.icon}
          label={typeof item.title === 'string' ? item.title : ''}
          segment={item.segment}
          mini={mini}
        />
      );
    }
    if (item.kind === 'link') {
      return (
        <NavItem
          key={item.href}
          icon={item.icon}
          label={item.title}
          href={item.href}
          external={item.external}
          mini={mini}
        />
      );
    }
    if (item.kind === 'action') {
      return (
        <NavItem
          key={item.action}
          icon={item.icon}
          label={item.title}
          mini={mini}
        />
      );
    }
    return null;
  };

  if (mini) {
    return (
      <Box
        component="nav"
        sx={{
          width: SIDEBAR_COLLAPSED_WIDTH,
          minWidth: SIDEBAR_COLLAPSED_WIDTH,
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          bgcolor: 'grey.50',
          transition: 'width 200ms ease, min-width 200ms ease',
          overflow: 'hidden',
          position: 'sticky',
          top: 0,
          py: 2,
          gap: 1,
        }}
      >
        <NavCompanyBranding mini onClick={handleCompanyMenuOpen} />
        <CompanyMenu
          anchorEl={companyMenuAnchor}
          open={Boolean(companyMenuAnchor)}
          onClose={handleCompanyMenuClose}
        />
        <Tooltip title="Expand sidebar" placement="right">
          <IconButton onClick={onToggle} size="small">
            <MenuIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Tooltip>
        <NavScrollArea sx={{ gap: 0.25, width: '100%', px: 1 }}>
          {groups.map((group, idx) => {
            const renderedItems = group.items.map(renderItem);
            if (group.header) {
              return (
                <NavCategoryHeader
                  key={group.header || idx}
                  title={group.header}
                  mini
                >
                  {renderedItems}
                </NavCategoryHeader>
              );
            }
            return (
              <React.Fragment key={`group-${idx}`}>
                {renderedItems}
              </React.Fragment>
            );
          })}
        </NavScrollArea>
        <SidebarFooter mini />
      </Box>
    );
  }

  return (
    <Box
      component="nav"
      sx={{
        width: SIDEBAR_EXPANDED_WIDTH,
        minWidth: SIDEBAR_EXPANDED_WIDTH,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        bgcolor: 'grey.50',
        transition: 'width 200ms ease, min-width 200ms ease',
        overflow: 'hidden',
        position: 'sticky',
        top: 0,
        px: 3.25,
        py: 3.75,
      }}
    >
      {/* Toggle button — absolute top-right */}
      <Tooltip title="Collapse sidebar" placement="left">
        <IconButton
          onClick={onToggle}
          size="small"
          sx={{
            position: 'absolute',
            top: 26,
            right: 14,
            borderRadius: 1.5,
            p: 1.5,
          }}
        >
          <LeftPanelCloseIcon sx={{ fontSize: 20, color: 'grey.500' }} />
        </IconButton>
      </Tooltip>

      {/* Top section */}
      <NavScrollArea>
        <Box sx={{ mb: 4 }}>
          <NavCompanyBranding onClick={handleCompanyMenuOpen} />
        </Box>
        <CompanyMenu
          anchorEl={companyMenuAnchor}
          open={Boolean(companyMenuAnchor)}
          onClose={handleCompanyMenuClose}
        />

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 0.75,
          }}
        >
          {groups.map((group, idx) => {
            const renderedItems = group.items.map(renderItem);

            if (group.header) {
              const isLastCategory = group.header.toLowerCase() === 'develop';
              return (
                <Box key={group.header || idx} sx={{ mt: 3.25 }}>
                  <NavCategoryHeader
                    title={group.header}
                    collapsible={isLastCategory}
                  >
                    {renderedItems}
                  </NavCategoryHeader>
                </Box>
              );
            }

            return (
              <React.Fragment key={`group-${idx}`}>
                {renderedItems}
              </React.Fragment>
            );
          })}
        </Box>
      </NavScrollArea>

      {/* Footer */}
      <SidebarFooter />
    </Box>
  );
}
