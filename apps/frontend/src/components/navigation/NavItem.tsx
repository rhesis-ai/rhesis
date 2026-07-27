'use client';

import React from 'react';
import NextLink from 'next/link';
import { usePathname } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import { BORDER_RADIUS } from '@/styles/theme';
import { type NavigationPageItem } from '@/types/navigation';
import { useCan } from '@/components/common/Can';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';
import { isActive, collapsedNavItemSx } from './sidebar-utils';

interface NavItemProps {
  item: NavigationPageItem;
  collapsed: boolean;
  parentPath?: string;
}

export function NavItem({ item, collapsed, parentPath = '' }: NavItemProps) {
  const pathname = usePathname();
  const fullPath = parentPath
    ? `${parentPath}/${item.segment}`
    : `/${item.segment}`;
  const active = isActive(pathname, fullPath);
  const ambient = useAmbientPermissions();
  const singlePermitted = useCan(item.requiredPermission ?? '');

  const requiredAnyOf = item.requiredAnyOf;
  const isGated = Boolean(requiredAnyOf?.length || item.requiredPermission);

  let permitted = true;
  if (requiredAnyOf?.length) {
    permitted =
      !ambient.enabled ||
      requiredAnyOf.some(p => ambient.permitted_actions.includes(p));
  } else if (item.requiredPermission) {
    permitted = singlePermitted;
  }

  if (isGated) {
    // Hide the item entirely, both while the RBAC status/scope set is still
    // resolving (avoid a flash of an item the user may not be allowed to see)
    // and once resolved if denied — a denied item is not rendered at all,
    // it isn't shown locked/disabled.
    if (ambient.loading) return null;
    if (!permitted) return null;
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
          {item.children?.map(child => (
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
