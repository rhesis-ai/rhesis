'use client';

import React from 'react';
import SettingsIcon from '@mui/icons-material/Settings';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import { useRouter } from 'next/navigation';
import MenuPopover from './MenuPopover';
import MenuListItem from './MenuListItem';

interface CompanyMenuProps {
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
}

export default function CompanyMenu({
  anchorEl,
  open,
  onClose,
}: CompanyMenuProps) {
  const router = useRouter();

  const handleNavigate = (path: string) => {
    router.push(path);
    onClose();
  };

  return (
    <MenuPopover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
    >
      <MenuListItem
        icon={<SettingsIcon sx={{ fontSize: 20 }} />}
        label="Settings"
        onClick={() => handleNavigate('/organizations/settings')}
      />
      <MenuListItem
        icon={<GroupAddIcon sx={{ fontSize: 20 }} />}
        label="Invite members"
        onClick={() => handleNavigate('/organizations/team')}
      />
    </MenuPopover>
  );
}
