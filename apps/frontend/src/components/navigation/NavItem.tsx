'use client';

import React from 'react';
import NextLink from 'next/link';
import { usePathname } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { BORDER_RADIUS } from '@/styles/theme';
import { type NavigationPageItem } from '@/types/navigation';
import { useCan } from '@/components/common/Can';
import { CAPABILITY_LABELS } from '@/constants/capabilities';
import { isActive, collapsedNavItemSx } from './sidebar-utils';

// MUI's default disabled opacity from theme.palette.action.disabledOpacity (0.38)
// expressed via sx so it scales with custom themes.
const LOCKED_OPACITY_SX = {
  opacity: (theme: import('@mui/material/styles').Theme) =>
    theme.palette.action.disabledOpacity,
};

interface NavItemProps {
  item: NavigationPageItem;
  collapsed: boolean;
  parentPath?: string;
}

function LockedNavItem({
  item,
  collapsed,
}: {
  item: NavigationPageItem;
  collapsed: boolean;
}) {
  const label = item.requiredPermission
    ? (CAPABILITY_LABELS[item.requiredPermission] ?? item.requiredPermission)
    : '';
  const tooltipTitle = collapsed
    ? `${item.title} — requires "${label}"`
    : `Requires "${label}"`;

  const inner = (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        ...(collapsed
          ? collapsedNavItemSx
          : { gap: '10px', px: '14px', py: '8px' }),
        borderRadius: BORDER_RADIUS.sm,
        cursor: 'not-allowed',
        ...LOCKED_OPACITY_SX,
      }}
    >
      {item.icon && (
        <Box
          sx={{
            display: 'flex',
            flexShrink: 0,
            color: theme => theme.palette.greyscale.body,
            '& svg': { width: 24, height: 24 },
          }}
        >
          {item.icon}
        </Box>
      )}
      {!collapsed && (
        <>
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: 400,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
              whiteSpace: 'nowrap',
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {item.title}
          </Typography>
          <Box sx={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
            <LockOutlinedIcon sx={{ fontSize: 14 }} />
          </Box>
        </>
      )}
    </Box>
  );

  return (
    <Tooltip title={tooltipTitle} placement="right">
      <Box component="span" sx={{ display: 'block' }}>
        {inner}
      </Box>
    </Tooltip>
  );
}

export function NavItem({ item, collapsed, parentPath = '' }: NavItemProps) {
  const pathname = usePathname();
  const fullPath = parentPath
    ? `${parentPath}/${item.segment}`
    : `/${item.segment}`;
  const active = isActive(pathname, fullPath);
  const permitted = useCan(item.requiredPermission ?? '');

  // Items with requiredPermission render locked when permission is absent.
  // useCan returns false while the scope set loads (fail-closed), so no flash.
  if (item.requiredPermission && !permitted) {
    return <LockedNavItem item={item} collapsed={collapsed} />;
  }

  const button = (
    <Box
      component={NextLink}
      href={fullPath}
      sx={{
        display: 'flex',
        alignItems: 'center',
        ...(collapsed
          ? collapsedNavItemSx
          : { gap: '10px', px: '14px', py: '8px' }),
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        cursor: 'pointer',
        bgcolor: active ? 'primary.dark' : 'transparent',
        '&:hover': {
          bgcolor: active
            ? 'primary.dark'
            : theme => theme.palette.greyscale.surface1,
        },
        transition: 'background-color 0.15s ease',
      }}
    >
      {item.icon && (
        <Box
          sx={{
            display: 'flex',
            flexShrink: 0,
            color: active
              ? 'primary.contrastText'
              : theme => theme.palette.greyscale.body,
            '& svg': { width: 24, height: 24 },
          }}
        >
          {item.icon}
        </Box>
      )}
      {!collapsed && (
        <>
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: active ? 600 : 400,
              lineHeight: '22px',
              color: active
                ? 'primary.contrastText'
                : theme => theme.palette.greyscale.body,
              whiteSpace: 'nowrap',
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {item.title}
          </Typography>
          {item.action && <Box sx={{ flexShrink: 0 }}>{item.action}</Box>}
        </>
      )}
    </Box>
  );

  const hasChildren = item.children && item.children.length > 0;

  const buttonNode = collapsed ? (
    <Tooltip title={item.title} placement="right">
      <Box component="span" sx={{ display: 'inline-flex' }}>
        {button}
      </Box>
    </Tooltip>
  ) : (
    button
  );

  if (!hasChildren) return buttonNode;

  return (
    <Box>
      {buttonNode}
      {!collapsed && (
        <Box
          sx={{
            pl: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            mt: '4px',
          }}
        >
          {item.children!.map(child => (
            <NavItem
              key={child.segment}
              item={child}
              collapsed={collapsed}
              parentPath={fullPath}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}

export default NavItem;
