'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import { ScienceIcon } from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';

interface TestsEmptyStateProps {
  onCreateTest: () => void;
  disabled?: boolean;
}

export default function TestsEmptyState({
  onCreateTest,
  disabled = false,
}: TestsEmptyStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2.5, // 20px
        py: 5, // 40px
        px: { xs: 3, sm: 6, md: 12, lg: 25 }, // up to 200px on large screens
        textAlign: 'center',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 1.25, // 10px
        }}
      >
        <ScienceIcon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Typography variant="h6" sx={{ color: 'primary.main' }}>
          No test yet
        </Typography>
      </Box>

      <Typography
        variant="body2"
        sx={{
          color: 'text.primary',
          maxWidth: 720,
        }}
      >
        Create your first test to start evaluating your AI endpoints. Tests let
        you measure quality, safety, and reliability across single-turn and
        multi-turn interactions.
      </Typography>

      <Button
        variant="outlined"
        color="primary"
        startIcon={<AddIcon />}
        onClick={onCreateTest}
        disabled={disabled}
        sx={{
          borderWidth: 2,
          borderRadius: BORDER_RADIUS.md,
          px: 2.5, // 20px
          py: 1.5, // 12px
          fontSize: theme => theme.typography.h6.fontSize,
          fontWeight: 700,
          lineHeight: '25px',
          '&:hover': { borderWidth: 2 },
        }}
      >
        Create test
      </Button>
    </Box>
  );
}
