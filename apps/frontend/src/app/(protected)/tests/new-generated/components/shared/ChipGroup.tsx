'use client';

import React, { useMemo } from 'react';
import { Box, Chip, Tooltip } from '@mui/material';
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

    return colorMap[chip.colorVariant || 'blue'] as any;
  };

  const getChipSx = (chip: ChipConfig) => {
    const baseSx: any = {
      transition: 'all 0.2s ease-in-out',
      cursor: 'pointer',
      '&:hover': {
        transform: 'translateY(-2px)',
        boxShadow: 1,
      },
    };

    // Add explicit background colors for filled warning and success chips in dark mode
    if (chip.active) {
      const colorVariant = chip.colorVariant || 'blue';
      if (colorVariant === 'orange') {
        baseSx.bgcolor = 'warning.main';
        baseSx.color = 'warning.contrastText';
        baseSx['&:hover'] = {
          ...baseSx['&:hover'],
          bgcolor: 'warning.dark',
        };
      } else if (colorVariant === 'green') {
        baseSx.bgcolor = 'success.main';
        baseSx.color = 'success.contrastText';
        baseSx['&:hover'] = {
          ...baseSx['&:hover'],
          bgcolor: 'success.dark',
        };
      }
    }

    if (variant === 'compact') {
      return {
        ...baseSx,
        '& .MuiChip-label': {
          fontSize: (theme: any) => theme.typography.caption.fontSize,
        },
        height: '24px',
      };
    }

    return baseSx;
  };

  // Cache the sort order (IDs only) based on initial chip structure
  // This prevents re-sorting when toggling but uses current chip data
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
  }, [chips.map(c => c.id).join(',')]);

  // Map the current chips according to the cached order
  const chipsMap = new Map(chips.map(c => [c.id, c]));
  const sortedChips = sortedOrder.map(id => chipsMap.get(id)!).filter(Boolean);

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
