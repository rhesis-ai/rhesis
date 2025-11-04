'use client';

import React from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  useTheme,
} from '@mui/material';
import ListIcon from '@mui/icons-material/List';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import BoltIcon from '@mui/icons-material/Bolt';

export type TestTypeFilter = 'all' | 'single-turn' | 'multi-turn';

interface TestsFilterBarProps {
  filter: TestTypeFilter;
  onFilterChange: (filter: TestTypeFilter) => void;
}

export default function TestsFilterBar({
  filter,
  onFilterChange,
}: TestsFilterBarProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: 'flex',
        mb: 2,
      }}
    >
      <ButtonGroup size="small" variant="outlined">
        <Button
          onClick={() => onFilterChange('all')}
          variant={filter === 'all' ? 'contained' : 'outlined'}
          startIcon={<ListIcon fontSize="small" />}
        >
          All
        </Button>
        <Button
          onClick={() => onFilterChange('single-turn')}
          variant={filter === 'single-turn' ? 'contained' : 'outlined'}
          startIcon={<BoltIcon fontSize="small" />}
          sx={{
            ...(filter === 'single-turn' && {
              backgroundColor: theme.palette.primary.main,
              '&:hover': {
                backgroundColor: theme.palette.primary.dark,
              },
            }),
          }}
        >
          Single-Turn
        </Button>
        <Button
          onClick={() => onFilterChange('multi-turn')}
          variant={filter === 'multi-turn' ? 'contained' : 'outlined'}
          startIcon={<AutorenewIcon fontSize="small" />}
          sx={{
            ...(filter === 'multi-turn' && {
              backgroundColor: theme.palette.secondary.main,
              '&:hover': {
                backgroundColor: theme.palette.secondary.dark,
              },
            }),
          }}
        >
          Multi-Turn
        </Button>
      </ButtonGroup>
    </Box>
  );
}

