'use client';

import React from 'react';
import { IconButton, IconButtonProps } from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';

interface GridFilterButtonProps extends Omit<IconButtonProps, 'onClick'> {
  onClick: () => void;
}

export default function GridFilterButton({
  onClick,
  sx,
  ...props
}: GridFilterButtonProps) {
  return (
    <IconButton
      onClick={onClick}
      sx={{
        width: 38,
        height: 38,
        bgcolor: 'primary.main',
        color: '#fff',
        borderRadius: 1,
        '&:hover': { bgcolor: 'primary.dark' },
        ...sx,
      }}
      {...props}
    >
      <TuneIcon sx={{ fontSize: 20 }} />
    </IconButton>
  );
}
