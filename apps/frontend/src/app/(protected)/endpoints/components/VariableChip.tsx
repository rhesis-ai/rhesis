'use client';

import React from 'react';
import { Box, Chip } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';
import { CheckIcon } from '@/components/icons';
import { insertableVariableChipSx } from './endpoint-styles';

interface VariableChipProps {
  label: string;
  isActive?: boolean;
  onClick?: (e: React.MouseEvent<HTMLElement>) => void;
  alignSelf?: string;
}

export default function VariableChip({
  label,
  isActive = false,
  onClick,
  alignSelf,
}: VariableChipProps) {
  return (
    <Chip
      label={
        isActive ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <span>{label}</span>
            <CheckIcon sx={{ fontSize: 11 }} />
          </Box>
        ) : (
          label
        )
      }
      size="small"
      onClick={onClick}
      sx={{
        ...insertableVariableChipSx,
        ...(alignSelf && { alignSelf }),
        ...(isActive && {
          bgcolor: (t: Theme) =>
            t.palette.mode === 'light'
              ? alpha(t.palette.success.main, 0.08)
              : alpha(t.palette.success.main, 0.18),
          color: 'success.main',
          borderColor: 'success.light',
        }),
      }}
    />
  );
}
