'use client';

import React, { ReactNode } from 'react';
import { Box, BoxProps } from '@mui/material';

interface GridToolbarActionsProps extends Omit<BoxProps, 'children'> {
  children: ReactNode;
}

export default function GridToolbarActions({
  children,
  sx,
  ...props
}: GridToolbarActionsProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        '& .MuiButton-root': {
          color: 'primary.main',
          fontSize: 14,
          fontWeight: 400,
          textTransform: 'none',
          px: 2,
          py: 1,
          borderRadius: (theme: any) => `${theme.customRadius.m}px`,
          '& .MuiButton-startIcon': {
            '& .MuiSvgIcon-root': { fontSize: 20 },
          },
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
}
