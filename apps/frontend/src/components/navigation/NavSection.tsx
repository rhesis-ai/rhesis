'use client';

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Collapse from '@mui/material/Collapse';
import Typography from '@mui/material/Typography';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import {
  type NavigationHeaderItem,
  type NavigationPageItem,
} from '@/types/navigation';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';
import { collapsedNavGroupSx } from './sidebar-utils';
import { NavItem } from './NavItem';

interface NavSectionProps {
  header: NavigationHeaderItem;
  items: NavigationPageItem[];
  collapsed: boolean;
}

export function NavSection({ header, items, collapsed }: NavSectionProps) {
  const isCollapsible = header.collapsible ?? false;
  const [sectionOpen, setSectionOpen] = useState(
    !(header.defaultCollapsed ?? false)
  );
  // Icon-only sidebar: always show section items (section headers are hidden).
  const showItems = collapsed || !isCollapsible || sectionOpen;

  // Each NavItem hides itself when its capability is denied. Mirror that
  // decision here (reading the ambient scope set once, not one hook per item)
  // so a section whose every item is hidden doesn't render an orphaned header
  // with an empty body. The membership logic matches `useCan`: fail-closed
  // while loading, permissive when RBAC is off, otherwise a set-membership check.
  const ambient = useAmbientPermissions();
  const hasVisibleItem = items.some(item => {
    if (!item.requiredPermission) return true;
    if (ambient.loading) return false;
    if (!ambient.enabled) return true;
    return ambient.permitted_actions.includes(item.requiredPermission);
  });
  if (!hasVisibleItem) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        ...(collapsed ? collapsedNavGroupSx : {}),
      }}
    >
      {!collapsed && (
        <ButtonBase
          onClick={isCollapsible ? () => setSectionOpen(o => !o) : undefined}
          tabIndex={isCollapsible ? 0 : -1}
          disableRipple={!isCollapsible}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: '14px',
            width: '100%',
            cursor: isCollapsible ? 'pointer' : 'default',
            userSelect: 'none',
          }}
        >
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 600,
              lineHeight: '18px',
              color: theme => theme.palette.greyscale.subtitle,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {header.title}
          </Typography>
          {isCollapsible && (
            <Box
              sx={{
                color: theme => theme.palette.greyscale.subtitle,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {sectionOpen ? (
                <KeyboardArrowUpIcon sx={{ fontSize: 20 }} />
              ) : (
                <KeyboardArrowDownIcon sx={{ fontSize: 20 }} />
              )}
            </Box>
          )}
        </ButtonBase>
      )}

      {/* Items — always visible when sidebar is collapsed, not collapsible, or toggled open */}
      <Collapse in={showItems} timeout="auto">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            ...(collapsed ? collapsedNavGroupSx : {}),
          }}
        >
          {items.map(item => (
            <NavItem key={item.segment} item={item} collapsed={collapsed} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export default NavSection;
