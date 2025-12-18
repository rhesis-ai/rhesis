/**
 * Centralized test run status utilities for consistent display
 * across dashboard, test-runs page, and other components.
 */
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

export type TestRunStatusColor =
  | 'success'
  | 'error'
  | 'warning'
  | 'info'
  | 'default';

/**
 * Get the color for a test run status
 * @param status - The test run status name (case-insensitive)
 * @returns Material-UI chip color
 */
export function getTestRunStatusColor(status?: string): TestRunStatusColor {
  if (!status) return 'default';

  const statusLower = status.toLowerCase();
  if (statusLower === 'completed') return 'success';
  if (statusLower === 'partial') return 'warning';
  if (statusLower === 'failed') return 'error';
  if (statusLower === 'progress') return 'info';

  return 'default';
}

/**
 * Get the icon component for a test run status
 * @param status - The test run status name (case-insensitive)
 * @param size - Icon size ('small', 'medium', or 'inherit')
 * @returns React icon component
 */
export function getTestRunStatusIcon(
  status?: string,
  size: 'small' | 'medium' | 'inherit' = 'small'
) {
  if (!status) return <PlayArrowIcon fontSize={size} />;

  const statusLower = status.toLowerCase();
  if (statusLower === 'completed')
    return <CheckCircleOutlineIcon fontSize={size} />;
  if (statusLower === 'partial')
    return <WarningAmberOutlinedIcon fontSize={size} />;
  if (statusLower === 'failed') return <CancelOutlinedIcon fontSize={size} />;
  if (statusLower === 'progress')
    return <PlayCircleOutlineIcon fontSize={size} />;

  return <PlayArrowIcon fontSize={size} />;
}

