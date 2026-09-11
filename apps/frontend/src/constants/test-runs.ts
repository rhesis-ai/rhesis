import type { ComponentType } from 'react';
import BlockIcon from '@mui/icons-material/Block';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';

export type RunStatus =
  | 'queued'
  | 'progress'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'cancelled';

export const RUN_STATUS_COLOR: Record<
  RunStatus,
  'default' | 'info' | 'warning' | 'success' | 'error'
> = {
  queued: 'default',
  progress: 'info',
  completed: 'success',
  partial: 'warning',
  failed: 'error',
  cancelled: 'default',
};

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: 'Queued',
  progress: 'In Progress',
  completed: 'Completed',
  partial: 'Partial',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export const RUN_STATUS_ICON: Record<RunStatus, ComponentType> = {
  queued: HourglassEmptyIcon,
  progress: PlayCircleOutlineIcon,
  completed: CheckCircleOutlineIcon,
  partial: WarningAmberOutlinedIcon,
  failed: CancelOutlinedIcon,
  cancelled: BlockIcon,
};

export function isTerminalRunStatus(status: string): boolean {
  return ['completed', 'partial', 'failed', 'cancelled'].includes(status);
}
