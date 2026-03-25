'use client';

import React, { useContext } from 'react';
import BrightnessAutoIcon from '@mui/icons-material/BrightnessAuto';
import LogoutIcon from '@mui/icons-material/Logout';
import { ColorModeContext } from '../providers/ThemeProvider';
import { signOut } from 'next-auth/react';
import MenuPopover from './MenuPopover';
import MenuListItem from './MenuListItem';

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
    <MenuPopover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
      transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
    >
      <MenuListItem
        icon={<BrightnessAutoIcon sx={{ fontSize: 20 }} />}
        label={mode === 'light' ? 'Dark Mode' : 'Light Mode'}
        onClick={handleToggleTheme}
      />
      <MenuListItem
        icon={<LogoutIcon sx={{ fontSize: 20 }} />}
        label="Sign Out"
        onClick={handleSignOut}
      />
    </MenuPopover>
  );
}
