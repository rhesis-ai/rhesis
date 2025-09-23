'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import ThemeToggle from '../common/ThemeToggle';
import AppVersion from '../common/AppVersion';
import { shouldShowGitInfo } from '@/utils/git-utils';

export default function ToolbarActions() {
  const showVersionInfo = shouldShowGitInfo();

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      {showVersionInfo && (
        <AppVersion 
          variant="caption"
          sx={{ 
            fontSize: '0.75rem',
            fontFamily: 'monospace',
            color: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(160, 160, 160, 0.8)'
          }}
        />
      )}
      <ThemeToggle />
    </Box>
  );
} 