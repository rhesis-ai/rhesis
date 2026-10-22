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
  /** Shown after the label, e.g. an info icon. */
  trailingIcon?: React.ReactNode;
  /** `primary`: light blue, body font — the Mapping step's variable list. */
  tone?: 'neutral' | 'primary';
}

export default function VariableChip({
  label,
  isActive = false,
  onClick,
  alignSelf,
  trailingIcon,
  tone = 'neutral',
}: VariableChipProps) {
  return (
    <Chip
      label={
        isActive || trailingIcon ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <span>{label}</span>
            {isActive && <CheckIcon sx={{ fontSize: 11 }} />}
            {trailingIcon}
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
        ...(tone === 'primary' && {
          fontFamily: 'inherit',
          fontSize: 13,
          height: 24,
          bgcolor: 'background.light2',
          color: 'greyscale.title',
        }),
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
