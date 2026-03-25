'use client';

import React, { ReactNode } from 'react';
import {
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListItemButtonProps,
} from '@mui/material';

interface MenuListItemProps extends Omit<ListItemButtonProps, 'children'> {
  icon: ReactNode;
  label: string;
  fontWeight?: number;
}

export default function MenuListItem({
  icon,
  label,
  fontWeight = 600,
  sx,
  ...props
}: MenuListItemProps) {
  return (
    <ListItemButton
      sx={{ borderRadius: 2, mx: 0.5, px: 1.5, ...sx }}
      {...props}
    >
      <ListItemIcon sx={{ minWidth: 32 }}>{icon}</ListItemIcon>
      <ListItemText
        primary={label}
        primaryTypographyProps={{ fontSize: 14, fontWeight }}
      />
    </ListItemButton>
  );
}
