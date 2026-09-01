'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  type NavigationLinkItem,
  type NavigationActionItem,
} from '@/types/navigation';
import {
  collapsedNavItemSx,
  NAV_CARD_ICON_SIZE,
  NAV_CARD_ROW_SX,
} from './sidebar-utils';

interface NavLinkItemProps {
  item: NavigationLinkItem | NavigationActionItem;
  collapsed: boolean;
  onAction?: (action: string) => void;
}

export function NavLinkItem({ item, collapsed, onAction }: NavLinkItemProps) {
  const isAction = item.kind === 'action';

  const sharedSx: SxProps<Theme> = {
    display: 'flex',
    alignItems: 'center',
    ...NAV_CARD_ROW_SX,
    py: '8px',
    borderRadius: BORDER_RADIUS.sm,
    textDecoration: 'none',
    cursor: 'pointer',
    '&:hover': {
      bgcolor: (theme: Theme) => theme.palette.greyscale.surface1,
    },
    // `duration.shortest` is the theme's own 150ms -- the value this used to
    // spell out as '0.15s'.
    transition: (theme: Theme) =>
      theme.transitions.create('background-color', {
        duration: theme.transitions.duration.shortest,
      }),
    ...(collapsed ? collapsedNavItemSx : {}),
  };

  const iconNode = item.icon && (
    <Box
      sx={{
        display: 'flex',
        flexShrink: 0,
        color: (theme: Theme) => theme.palette.greyscale.body,
        '& svg': { width: NAV_CARD_ICON_SIZE, height: NAV_CARD_ICON_SIZE },
      }}
    >
      {item.icon}
    </Box>
  );

  const labelNode = !collapsed && (
    <>
      <Typography
        sx={{
          fontSize: 14,
          fontWeight: 400,
          lineHeight: '22px',
          color: (theme: Theme) => theme.palette.greyscale.body,
          whiteSpace: 'nowrap',
          flex: 1,
        }}
      >
        {item.title}
      </Typography>
      {!isAction && (item as NavigationLinkItem).external && (
        <OpenInNewIcon
          sx={{
            fontSize: 14,
            color: (theme: Theme) => theme.palette.greyscale.subtitle,
            flexShrink: 0,
          }}
        />
      )}
    </>
  );

  const button = isAction ? (
    <Box
      component="button"
      type="button"
      onClick={() => onAction?.((item as NavigationActionItem).action)}
      sx={{
        ...sharedSx,
        background: 'none',
        border: 'none',
        alignSelf: 'stretch',
        textAlign: 'left',
      }}
    >
      {iconNode}
      {labelNode}
    </Box>
  ) : (
    <Box
      component="a"
      href={(item as NavigationLinkItem).href}
      target={(item as NavigationLinkItem).external ? '_blank' : undefined}
      rel={
        (item as NavigationLinkItem).external
          ? 'noopener noreferrer'
          : undefined
      }
      sx={sharedSx}
    >
      {iconNode}
      {labelNode}
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
