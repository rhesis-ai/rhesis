'use client';

import React, { useContext } from 'react';
import {
  Popover,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import BrightnessAutoIcon from '@mui/icons-material/BrightnessAuto';
import LogoutIcon from '@mui/icons-material/Logout';
import { ColorModeContext } from '../providers/ThemeProvider';
import { signOut } from 'next-auth/react';

interface UserMenuProps {
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
}

export default function UserMenu({ anchorEl, open, onClose }: UserMenuProps) {
  const { toggleColorMode, mode } = useContext(ColorModeContext);

  const handleToggleTheme = () => {
    toggleColorMode();
    onClose();
  };

  const handleSignOut = () => {
    onClose();
    signOut({ callbackUrl: '/' });
  };

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
      transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      slotProps={{
        paper: {
          sx: {
            bgcolor: 'grey.200',
            borderRadius: 4,
            boxShadow:
              '0px 2px 8px rgba(0, 0, 0, 0.08), 0px 0px 1px rgba(0, 0, 0, 0.3)',
            mb: 0.5,
            minWidth: 200,
          },
        },
      }}
    >
      <List disablePadding sx={{ py: 0.5 }}>
        <ListItemButton
          onClick={handleToggleTheme}
          sx={{ borderRadius: 2, mx: 0.5, px: 1.5 }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <BrightnessAutoIcon sx={{ fontSize: 20 }} />
          </ListItemIcon>
          <ListItemText
            primary={mode === 'light' ? 'Dark Mode' : 'Light Mode'}
            primaryTypographyProps={{ fontSize: 14, fontWeight: 600 }}
          />
        </ListItemButton>
        <ListItemButton
          onClick={handleSignOut}
          sx={{ borderRadius: 2, mx: 0.5, px: 1.5 }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <LogoutIcon sx={{ fontSize: 20 }} />
          </ListItemIcon>
          <ListItemText
            primary="Sign Out"
            primaryTypographyProps={{ fontSize: 14, fontWeight: 600 }}
          />
        </ListItemButton>
      </List>
    </Popover>
  );
}
