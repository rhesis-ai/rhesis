'use client';

import React from 'react';
import { Fab, Tooltip } from '@mui/material';

interface FloatingActionButtonProps {
  icon: React.ReactNode;
  onClick?: () => void;
  tooltip?: string;
  color?: 'primary' | 'secondary' | 'default';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
}

export default function FloatingActionButton({
  icon,
  onClick,
  tooltip,
  color = 'primary',
  size = 'small',
  disabled = false,
}: FloatingActionButtonProps) {
  const fab = (
    <Fab
      color={color}
      onClick={onClick}
      disabled={disabled}
      size={size}
      sx={{
        width: 44,
        height: 44,
        minHeight: 44,
        boxShadow: (theme: any) => theme.shadows[2],
        '&:hover': {
          boxShadow: (theme: any) => theme.shadows[4],
        },
        '& .MuiSvgIcon-root': { fontSize: 24 },
      }}
    >
      {icon}
    </Fab>
  );

  if (tooltip) {
    return <Tooltip title={tooltip}>{fab}</Tooltip>;
  }

  return fab;
}
