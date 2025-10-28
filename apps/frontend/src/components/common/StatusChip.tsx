'use client';

import React from 'react';
import { Chip, ChipProps } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

export type TestResultStatus = 'Pass' | 'Fail' | 'Error';

export interface StatusChipProps extends Omit<ChipProps, 'icon' | 'color'> {
  /**
   * Whether the status represents a passed/successful state (legacy, use status instead)
   * @deprecated Use status prop instead
   */
  passed?: boolean;
  /**
   * The status of the test result: Pass, Fail, or Error
   */
  status?: TestResultStatus;
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
 * A standardized status chip component that displays pass/fail/error states
 * with consistent icons and colors across the application.
 */
export default function StatusChip({
  passed,
  status,
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

  // Determine status from either new status prop or legacy passed prop
  const actualStatus: TestResultStatus =
    status || (passed !== undefined ? (passed ? 'Pass' : 'Fail') : 'Error');

  // Determine icon based on status
  const getIcon = () => {
    switch (actualStatus) {
      case 'Pass':
        return <CheckCircleOutlineIcon sx={{ fontSize: finalIconSize }} />;
      case 'Fail':
        return <CancelOutlinedIcon sx={{ fontSize: finalIconSize }} />;
      case 'Error':
        return <ErrorOutlineIcon sx={{ fontSize: finalIconSize }} />;
      default:
        return <CancelOutlinedIcon sx={{ fontSize: finalIconSize }} />;
    }
  };

  // Determine color based on status
  const getColor = (): ChipProps['color'] => {
    switch (actualStatus) {
      case 'Pass':
        return 'success';
      case 'Fail':
        return 'error';
      case 'Error':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Chip
      icon={getIcon()}
      label={label}
      size={size}
      color={getColor()}
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
