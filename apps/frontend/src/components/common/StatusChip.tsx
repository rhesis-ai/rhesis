'use client';

import React from 'react';
import { Chip, ChipProps } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';

export interface StatusChipProps extends Omit<ChipProps, 'icon' | 'color'> {
  /**
   * Whether the status represents a passed/successful state
   */
  passed: boolean;
  /**
   * The text to display in the chip
   */
  label: string;
  /**
   * Size of the chip and its icon
   */
  size?: 'small' | 'medium';
  /**
   * Variant of the chip
   */
  variant?: 'filled' | 'outlined';
  /**
   * Custom icon size (defaults based on chip size)
   */
  iconSize?: number;
}

/**
 * A standardized status chip component that displays pass/fail states
 * with consistent icons and colors across the application.
 */
export default function StatusChip({
  passed,
  label,
  size = 'small',
  variant = 'outlined',
  iconSize,
  sx,
  ...chipProps
}: StatusChipProps) {
  // Determine icon size based on chip size if not explicitly provided
  const defaultIconSize = size === 'small' ? 16 : 20;
  const finalIconSize = iconSize ?? defaultIconSize;

  return (
    <Chip
      icon={
        passed ? (
          <CheckCircleOutlineIcon sx={{ fontSize: finalIconSize }} />
        ) : (
          <CancelOutlinedIcon sx={{ fontSize: finalIconSize }} />
        )
      }
      label={label}
      size={size}
      color={passed ? 'success' : 'error'}
      variant={variant}
      sx={sx}
      {...chipProps}
    />
  );
}

/**
 * Helper function to create a status chip with metric counts
 */
export function MetricStatusChip({
  passedCount,
  totalCount,
  size = 'small',
  variant = 'outlined',
  ...chipProps
}: {
  passedCount: number;
  totalCount: number;
  size?: 'small' | 'medium';
  variant?: 'filled' | 'outlined';
} & Omit<ChipProps, 'icon' | 'color' | 'label'>) {
  const passed = totalCount > 0 && passedCount === totalCount;
  const label = `${passed ? 'Passed' : 'Failed'} (${passedCount}/${totalCount})`;

  return (
    <StatusChip
      passed={passed}
      label={label}
      size={size}
      variant={variant}
      {...chipProps}
    />
  );
}

/**
 * Helper function to create a simple pass/fail status chip
 */
export function SimpleStatusChip({
  passed,
  size = 'small',
  variant = 'outlined',
  ...chipProps
}: {
  passed: boolean;
  size?: 'small' | 'medium';
  variant?: 'filled' | 'outlined';
} & Omit<ChipProps, 'icon' | 'color' | 'label'>) {
  return (
    <StatusChip
      passed={passed}
      label={passed ? 'Passed' : 'Failed'}
      size={size}
      variant={variant}
      {...chipProps}
    />
  );
}
