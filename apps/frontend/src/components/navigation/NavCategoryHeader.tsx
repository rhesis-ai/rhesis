'use client';

import React, { useState } from 'react';
import { Box, Typography, Collapse } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';

export interface NavCategoryHeaderProps {
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  collapsible?: boolean;
  mini?: boolean;
}

export default function NavCategoryHeader({
  title,
  children,
  defaultExpanded = true,
  collapsible = false,
  mini = false,
}: NavCategoryHeaderProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (mini) {
    return <>{children}</>;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      <Box
        onClick={collapsible ? () => setExpanded(!expanded) : undefined}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.75,
          cursor: collapsible ? 'pointer' : 'default',
          userSelect: 'none',
          height: 24,
        }}
      >
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 600,
            lineHeight: '18px',
            textTransform: 'uppercase',
            color: 'grey.500',
          }}
        >
          {title}
        </Typography>
        {collapsible &&
          (expanded ? (
            <KeyboardArrowUpIcon sx={{ fontSize: 24, color: 'grey.500' }} />
          ) : (
            <KeyboardArrowDownIcon sx={{ fontSize: 24, color: 'grey.500' }} />
          ))}
      </Box>
      <Collapse in={collapsible ? expanded : true}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}
