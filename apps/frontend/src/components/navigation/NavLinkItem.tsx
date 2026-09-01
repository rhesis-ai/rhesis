'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import type { SxProps, Theme } from '@mui/material/styles';
import {
  type NavigationLinkItem,
  type NavigationActionItem,
} from '@/types/navigation';
import {
  collapsedNavItemSx,
  navCardIconSx,
  navCardLabelSx,
  navCardRowSx,
} from './sidebar-utils';

interface NavLinkItemProps {
  item: NavigationLinkItem | NavigationActionItem;
  collapsed: boolean;
  onAction?: (action: string) => void;
}

export function NavLinkItem({ item, collapsed, onAction }: NavLinkItemProps) {
  const isAction = item.kind === 'action';

  const sharedSx: SxProps<Theme> = {
    ...navCardRowSx(),
    ...(collapsed ? collapsedNavItemSx : {}),
  };

  const iconNode = item.icon && (
    <Box
      sx={{
        ...navCardIconSx,
        color: (theme: Theme) => theme.palette.greyscale.body,
      }}
    >
      {item.icon}
    </Box>
  );

  const labelNode = !collapsed && (
    <>
      <Typography
        sx={{
          ...navCardLabelSx,
          color: (theme: Theme) => theme.palette.greyscale.body,
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
