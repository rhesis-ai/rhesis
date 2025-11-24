/**
 * Utility functions for consistent status color mapping across the application
 */

export type StatusColor = 'success' | 'error' | 'warning' | 'info' | 'default';

/**
 * Maps status names to Material-UI chip colors
 * @param statusName - The status name (case-insensitive)
 * @returns The appropriate Material-UI color
 */
export function getStatusColor(statusName: string): StatusColor {
  const name = statusName.toLowerCase();
  
  // Active/Success states
  if (name === 'active' || name === 'completed' || name === 'success') {
    return 'success';
  }
  
  // Error/Failed states
  if (name === 'error' || name === 'failed' || name === 'failure') {
    return 'error';
  }
  
  // Warning/Pending states
  if (name === 'pending' || name === 'in progress' || name === 'progress' || name === 'partial') {
    return 'warning';
  }
  
  // Info states
  if (name === 'info' || name === 'running') {
    return 'info';
  }
  
  // Default for unknown states
  return 'default';
}

/**
 * Maps status names to theme color paths for use with sx prop
 * @param statusName - The status name (case-insensitive)
 * @returns The theme color path
 */
export function getStatusThemeColor(statusName: string): string {
  const color = getStatusColor(statusName);
  
  switch (color) {
    case 'success':
      return 'success.main';
    case 'error':
      return 'error.main';
    case 'warning':
      return 'warning.main';
    case 'info':
      return 'info.main';
    default:
      return 'text.secondary';
  }
}
