'use client';

import React, { useMemo } from 'react';
import { Box, Chip, Tooltip, type Theme } from '@mui/material';
import type { SxProps } from '@mui/system';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { ChipConfig } from './types';

interface ChipGroupProps {
  chips: ChipConfig[];
  onToggle: (chipId: string) => void;
  variant?: 'default' | 'compact';
}

/**
 * ChipGroup Component
 * Displays a group of toggleable chips with active/inactive states
 */
export default function ChipGroup({
  chips,
  onToggle,
  variant = 'default',
}: ChipGroupProps) {
  const getChipColor = (chip: ChipConfig) => {
    if (!chip.active) {
      return undefined; // Default MUI outlined chip color
    }

    // Map color variants to MUI theme colors
    const colorMap: Record<string, string> = {
      blue: 'primary',
      purple: 'secondary',
      orange: 'warning',
      green: 'success',
    };

    return colorMap[chip.colorVariant || 'blue'] as
      | 'primary'
      | 'secondary'
      | 'warning'
      | 'success'
      | undefined;
  };

  const getChipSx = (chip: ChipConfig) => {
    const baseSx: SxProps<Theme> = {
      cursor: 'pointer',
    };

    // Add explicit background colors for filled warning and success chips in dark mode
    if (chip.active) {
      const colorVariant = chip.colorVariant || 'blue';
      if (colorVariant === 'orange') {
        return {
          ...baseSx,
          bgcolor: 'warning.main',
          color: 'warning.contrastText',
          '&:hover': { bgcolor: 'warning.dark' },
          ...(variant === 'compact'
            ? {
                '& .MuiChip-label': {
                  fontSize: (theme: Theme) => theme.typography.caption.fontSize,
                },
                height: '24px',
              }
            : {}),
        };
      } else if (colorVariant === 'green') {
        return {
          ...baseSx,
          bgcolor: 'success.main',
          color: 'success.contrastText',
          '&:hover': { bgcolor: 'success.dark' },
          ...(variant === 'compact'
            ? {
                '& .MuiChip-label': {
                  fontSize: (theme: Theme) => theme.typography.caption.fontSize,
                },
                height: '24px',
              }
            : {}),
        };
      }
    }

    if (variant === 'compact') {
      return {
        ...baseSx,
        '& .MuiChip-label': {
          fontSize: (theme: Theme) => theme.typography.caption.fontSize,
        },
        height: '24px',
      };
    }

    return baseSx;
  };

  // Cache the sort order (IDs only) based on initial chip structure
  // This prevents re-sorting when toggling but uses current chip data
  const chipIdKey = chips.map(c => c.id).join(',');
  const sortedOrder = useMemo(() => {
    const sorted = [...chips].sort((a, b) => {
      // First sort by active status (active first)
      if (a.active !== b.active) {
        return a.active ? -1 : 1;
      }
      // Then sort alphabetically by label within each group
      return a.label.localeCompare(b.label);
    });
    return sorted.map(c => c.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chipIdKey]);

  // Map the current chips according to the cached order
  const chipsMap = new Map(chips.map(c => [c.id, c]));
  const sortedChips = sortedOrder
    .map(id => chipsMap.get(id))
    .filter((chip): chip is ChipConfig => chip !== undefined);

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 1,
        alignItems: 'center',
      }}
    >
      {sortedChips.map(chip => {
        const chipLabel = chip.description ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <span>{chip.label}</span>
            <Tooltip title={chip.description} arrow placement="top">
              <InfoOutlinedIcon
                sx={{
                  fontSize: 14,
                  opacity: 0.7,
                  cursor: 'help',
                }}
              />
            </Tooltip>
          </Box>
        ) : (
          chip.label
        );

        return (
          <Chip
            key={chip.id}
            label={chipLabel}
            onClick={() => onToggle(chip.id)}
            variant={chip.active ? 'filled' : 'outlined'}
            color={getChipColor(chip)}
            size={variant === 'compact' ? 'small' : 'medium'}
            sx={getChipSx(chip)}
          />
        );
      })}
    </Box>
  );
}
