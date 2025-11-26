'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { Account } from '@toolpad/core/Account';
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
            fontSize: theme =>
              `calc(${theme.typography.caption.fontSize || '0.75rem'} * 0.93)`, // ~0.7rem
            fontFamily: 'monospace',
            color: theme =>
              theme.palette.mode === 'dark'
                ? theme.palette.text.primary
                : theme.palette.primary.contrastText,
          }}
        />
      )}
      <ThemeToggle />
      <Account />
    </Box>
  );
}
