'use client';

import React from 'react';
import {
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
} from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';

export interface NavItemProps {
  icon?: React.ReactNode;
  label: string;
  segment?: string;
  href?: string;
  external?: boolean;
  active?: boolean;
  mini?: boolean;
  onClick?: () => void;
}

export default function NavItem({
  icon,
  label,
  segment,
  href,
  external,
  active: activeProp,
  mini = false,
  onClick,
}: NavItemProps) {
  const router = useRouter();
  const pathname = usePathname();

  const isActive =
    activeProp ??
    (segment
      ? pathname === `/${segment}` || pathname?.startsWith(`/${segment}/`)
      : false);

  const handleClick = () => {
    if (onClick) {
      onClick();
      return;
    }
    if (href && external) {
      window.open(href, '_blank', 'noopener,noreferrer');
      return;
    }
    if (href) {
      router.push(href);
      return;
    }
    if (segment) {
      router.push(`/${segment}`);
    }
  };

  const button = (
    <ListItemButton
      onClick={handleClick}
      selected={isActive}
      sx={{
        borderRadius: 1,
        px: 1.75,
        py: 1,
        minHeight: 38,
        justifyContent: mini ? 'center' : 'flex-start',
        '&.Mui-selected': {
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          '&:hover': {
            bgcolor: 'primary.light',
          },
          '& .MuiListItemIcon-root': {
            color: 'primary.contrastText',
          },
          '& .MuiListItemText-primary': {
            color: 'primary.contrastText',
          },
        },
        '&:hover:not(.Mui-selected)': {
          bgcolor: 'grey.200',
        },
      }}
    >
      {icon && (
        <ListItemIcon
          sx={{
            minWidth: mini ? 0 : 34,
            color: isActive ? 'primary.contrastText' : 'grey.800',
            justifyContent: 'center',
            '& .MuiSvgIcon-root': {
              fontSize: 24,
            },
          }}
        >
          {icon}
        </ListItemIcon>
      )}
      {!mini && (
        <ListItemText
          primary={label}
          primaryTypographyProps={{
            fontSize: 14,
            fontWeight: 400,
            lineHeight: '22px',
            noWrap: true,
          }}
        />
      )}
    </ListItemButton>
  );

  if (mini) {
    return (
      <Tooltip title={label} placement="right">
        {button}
      </Tooltip>
    );
  }

  return button;
}
