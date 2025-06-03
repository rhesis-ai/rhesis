'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import ThemeToggle from '../common/ThemeToggle';

export default function ToolbarActions() {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <ThemeToggle />
    </Box>
  );
} 