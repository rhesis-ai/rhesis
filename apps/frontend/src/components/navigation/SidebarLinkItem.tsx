'use client';

import React, { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';

interface SidebarLinkItemProps {
  href: string;
  icon: ReactNode;
  label: string;
}

export default function SidebarLinkItem({
  href,
  icon,
  label,
}: SidebarLinkItemProps) {
  return (
    <Box
      component="a"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        textDecoration: 'none',
        color: 'text.secondary',
        px: 1.75,
        py: 1,
        borderRadius: (theme: any) => `${theme.customRadius.m}px`,
        '&:hover': { bgcolor: 'grey.200' },
      }}
    >
      {icon}
      <Typography fontSize={14} lineHeight="22px">
        {label}
      </Typography>
    </Box>
  );
}
