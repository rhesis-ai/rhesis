'use client';

import React from 'react';
import { Box, Paper } from '@mui/material';

interface DataCardProps {
  toolbarLeft?: React.ReactNode;
  toolbarCenter?: React.ReactNode;
  toolbarRight?: React.ReactNode;
  toolbar?: React.ReactNode;
  children: React.ReactNode;
}

export default function DataCard({
  toolbarLeft,
  toolbarCenter,
  toolbarRight,
  toolbar,
  children,
}: DataCardProps) {
  const hasToolbar = toolbar || toolbarLeft || toolbarCenter || toolbarRight;

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: 'grey.300',
        boxShadow:
          '0px 2px 8px rgba(0, 0, 0, 0.04), 0px 0px 1px rgba(0, 0, 0, 0.12)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {hasToolbar && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2.5,
            py: 1.5,
          }}
        >
          {toolbar || (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                {toolbarLeft}
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {toolbarCenter}
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                }}
              >
                {toolbarRight}
              </Box>
            </>
          )}
        </Box>
      )}
      <Box sx={{ flex: 1, minHeight: 0 }}>{children}</Box>
    </Paper>
  );
}
