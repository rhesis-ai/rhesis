'use client';

import React, { ReactNode } from 'react';
import { Box, BoxProps } from '@mui/material';

interface NavScrollAreaProps extends Omit<BoxProps, 'children'> {
  children: ReactNode;
}

export default function NavScrollArea({
  children,
  sx,
  ...props
}: NavScrollAreaProps) {
  return (
    <Box
      sx={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        '&::-webkit-scrollbar': { width: 4 },
        '&::-webkit-scrollbar-thumb': {
          bgcolor: 'grey.300',
          borderRadius: (theme: any) => `${theme.customRadius.xl}px`,
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
}
