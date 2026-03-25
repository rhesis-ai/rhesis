'use client';

import React from 'react';
import {
  Popover,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import { useRouter } from 'next/navigation';

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
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      slotProps={{
        paper: {
          sx: {
            bgcolor: 'grey.200',
            borderRadius: 2,
            boxShadow:
              '0px 2px 8px rgba(0, 0, 0, 0.08), 0px 0px 1px rgba(0, 0, 0, 0.3)',
            mt: 0.5,
            minWidth: 200,
          },
        },
      }}
    >
      <List disablePadding sx={{ py: 0.5 }}>
        <ListItemButton
          onClick={() => handleNavigate('/organizations/settings')}
          sx={{ borderRadius: 2, mx: 0.5, px: 1.5 }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <SettingsIcon sx={{ fontSize: 20 }} />
          </ListItemIcon>
          <ListItemText
            primary="Settings"
            primaryTypographyProps={{ fontSize: 14 }}
          />
        </ListItemButton>
        <ListItemButton
          onClick={() => handleNavigate('/organizations/team')}
          sx={{ borderRadius: 2, mx: 0.5, px: 1.5 }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <GroupAddIcon sx={{ fontSize: 20 }} />
          </ListItemIcon>
          <ListItemText
            primary="Invite members"
            primaryTypographyProps={{ fontSize: 14 }}
          />
        </ListItemButton>
      </List>
    </Popover>
  );
}
