'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { BORDER_RADIUS } from '@/styles/theme';
import { type NavigationLinkItem } from '@/types/navigation';
import { collapsedNavItemSx } from './sidebar-utils';

interface NavLinkItemProps {
  item: NavigationLinkItem;
  collapsed: boolean;
}

export function NavLinkItem({ item, collapsed }: NavLinkItemProps) {
  const button = (
    <Box
      component="a"
      href={item.href}
      target={item.external ? '_blank' : undefined}
      rel={item.external ? 'noopener noreferrer' : undefined}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        px: '14px',
        py: '8px',
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        cursor: 'pointer',
        '&:hover': {
          bgcolor: theme => theme.palette.greyscale.surface1,
        },
        transition: 'background-color 0.15s ease',
        ...(collapsed ? collapsedNavItemSx : {}),
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
            }}
          >
            {item.title}
          </Typography>
          {item.external && (
            <OpenInNewIcon
              sx={{
                fontSize: 14,
                color: theme => theme.palette.greyscale.subtitle,
                flexShrink: 0,
              }}
            />
          )}
        </>
      )}
    </Box>
  );

  return collapsed ? (
    <Tooltip title={item.title} placement="right">
      {button}
    </Tooltip>
  ) : (
    button
  );
}

export default NavLinkItem;
