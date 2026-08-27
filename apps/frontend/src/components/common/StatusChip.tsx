'use client';

import React from 'react';
import { Chip, ChipProps } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { BORDER_RADIUS } from '@/styles/theme';
import { STATUS_LABEL, type TestResultStatus } from '@/constants/outcomes';

// The canonical vocabulary lives in constants/outcomes.ts (mirroring the
// backend enum), not in this presentational component. Re-exported so the
// many existing `from '@/components/common/StatusChip'` type imports keep
// working.
export type { TestResultStatus };

export interface StatusChipProps extends Omit<ChipProps, 'icon' | 'color'> {
  /**
   * Whether the status represents a passed/successful state (legacy, use status instead)
   * @deprecated Use status prop instead
   */
  passed?: boolean;
  /**
   * The status of the test result: Pass, Fail, Error, or Inconclusive
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

  // Determine status from either new status prop or legacy passed prop.
  // Neither given is a caller bug, not an errored result -- rendering it as
  // Error used to silently turn "I forgot to pass a prop" into a real-looking
  // failure state.
  const actualStatus: TestResultStatus = status ?? (passed ? 'Pass' : 'Fail');

  // Determine icon based on status
  const iconSx = { fontSize: finalIconSize, color: 'inherit' };

  const getIcon = () => {
    switch (actualStatus) {
      case 'Pass':
        return <CheckCircleOutlineIcon sx={iconSx} />;
      case 'Fail':
        return <CancelOutlinedIcon sx={iconSx} />;
      case 'Error':
        return <ErrorOutlineIcon sx={iconSx} />;
      case 'Inconclusive':
        return <HelpOutlineIcon sx={iconSx} />;
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
      case 'Inconclusive':
        // Neutral rather than warning: the evaluation worked fine, it just
        // has no pass/fail to report. Colouring it like an error would
        // reintroduce exactly the conflation this state exists to remove.
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
      sx={{
        borderRadius: BORDER_RADIUS.pill,
        fontSize: '0.75rem', // Intentional: caption size for status badges
        ...sx,
      }}
      {...chipProps}
    />
  );
}

/**
 * A chip summarising how many of an entity's metrics passed, e.g.
 * "Passed (3/3)".
 *
 * This is a per-metric tally, deliberately NOT the entity's own outcome:
 * `status` should be the backend-computed one (via `displayStatusOf`), so a
 * result whose metrics all pass but which errored, or which a human reviewed
 * down to Fail, still reads correctly. Omitting `status` falls back to the
 * count, which is only right where no outcome is available.
 */
export function MetricStatusChip({
  passedCount,
  totalCount,
  status,
  size = 'small',
  variant = 'outlined',
  ...chipProps
}: {
  passedCount: number;
  totalCount: number;
  status?: TestResultStatus;
  size?: 'small' | 'medium';
  variant?: 'filled' | 'outlined';
} & Omit<ChipProps, 'icon' | 'color' | 'label'>) {
  const actualStatus: TestResultStatus =
    status ?? (totalCount > 0 && passedCount === totalCount ? 'Pass' : 'Fail');
  const label = `${STATUS_LABEL[actualStatus]} (${passedCount}/${totalCount})`;

  return (
    <StatusChip
      status={actualStatus}
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
  const status: TestResultStatus = passed ? 'Pass' : 'Fail';
  return (
    <StatusChip
      status={status}
      label={STATUS_LABEL[status]}
      size={size}
      variant={variant}
      {...chipProps}
    />
  );
}
